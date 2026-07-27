"""Render a :class:`DrawingScene` as self-contained SVG."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import hypot
from xml.etree import ElementTree as ET

from ..scene import (
    Box,
    DrawingScene,
    Point,
    SceneConnector,
    SceneContainer,
    SceneShape,
    SceneText,
)
from ..styles import ElementStyle, normalize_color
from ..typography import FontSize

_SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", _SVG_NS)

_THEME_COLORS = {
    "background1": "#FFFFFF",
    "text1": "#000000",
    "background2": "#E7E6E6",
    "text2": "#44546A",
    "accent1": "#4472C4",
    "accent2": "#ED7D31",
    "accent3": "#A5A5A5",
    "accent4": "#FFC000",
    "accent5": "#5B9BD5",
    "accent6": "#70AD47",
    "hyperlink": "#0563C1",
    "followed_hyperlink": "#954F72",
}
_DASH_ARRAYS = {
    "dash": "7 5",
    "dashed": "7 5",
    "dot": "2 4",
    "dotted": "2 4",
    "dashdot": "7 4 2 4",
    "dash-dot": "7 4 2 4",
}


@dataclass(frozen=True, slots=True)
class SvgRenderResult:
    """Serialized SVG plus its output viewport dimensions."""

    svg: str
    width_px: int
    height_px: int


class SvgRenderer:
    """Serialize renderer-neutral shapes without scripts or external assets."""

    def render(
        self,
        scene: DrawingScene,
        *,
        width_px: int | None = None,
        height_px: int | None = None,
        background: str | None = None,
    ) -> SvgRenderResult:
        """Return self-contained SVG while preserving the scene aspect ratio."""

        scene.recompute_extents()
        logical_width = max(scene.width, 0.001)
        logical_height = max(scene.height, 0.001)
        natural_scale = 1.0 if scene.metadata.get("coordinate_units") == "svg_px" else 96.0
        natural_width = max(1, round(logical_width * natural_scale))
        natural_height = max(1, round(logical_height * natural_scale))
        resolved_width, resolved_height = _resolve_dimensions(
            natural_width,
            natural_height,
            width_px,
            height_px,
        )

        root = ET.Element(
            _tag("svg"),
            {
                "width": str(resolved_width),
                "height": str(resolved_height),
                "viewBox": f"0 0 {_num(logical_width)} {_num(logical_height)}",
                "preserveAspectRatio": "xMidYMid meet",
                "role": "img",
                "aria-label": f"{scene.kind} diagram",
            },
        )
        ET.SubElement(root, _tag("title")).text = f"{scene.kind} diagram"
        defs = ET.SubElement(root, _tag("defs"))
        points_to_units = (
            96.0 / 72.0 if scene.metadata.get("coordinate_units") == "svg_px" else 1.0 / 72.0
        )
        if background and normalize_color(background) not in {"none", "transparent", "#00000000"}:
            color, opacity = _color(background)
            attributes = {
                "x": "0",
                "y": "0",
                "width": _num(logical_width),
                "height": _num(logical_height),
                "fill": color,
            }
            if opacity < 1:
                attributes["fill-opacity"] = _num(opacity)
            ET.SubElement(root, _tag("rect"), attributes)

        for index, element in enumerate(scene.ordered_elements()):
            if isinstance(element, SceneContainer):
                self._container(root, element, points_to_units)
            elif isinstance(element, SceneConnector):
                self._connector(root, defs, element, index, points_to_units)
            elif isinstance(element, SceneShape):
                self._shape(root, element, points_to_units)
            elif isinstance(element, SceneText):
                self._standalone_text(root, element, points_to_units)

        svg = ET.tostring(root, encoding="unicode", xml_declaration=True)
        return SvgRenderResult(svg=svg, width_px=resolved_width, height_px=resolved_height)

    def _container(self, root: ET.Element, item: SceneContainer, points_to_units: float) -> None:
        group = _semantic_group(root, item.semantic_id, item.role)
        stroke, stroke_opacity = _color(item.style.line or "#8FA4B8", item.style.opacity)
        attributes = {
            **_box_attributes(item.box),
            "fill": "none",
            "stroke": stroke,
            "stroke-width": _stroke_width(item.style, points_to_units),
            "rx": "0"
            if item.role.startswith("sequence.fragment.")
            else _num(min(item.box.width, item.box.height) * 0.06),
        }
        if stroke_opacity < 1:
            attributes["stroke-opacity"] = _num(stroke_opacity)
        dash = item.style.dash
        if dash is None and not item.role.startswith("sequence.fragment."):
            dash = "dash"
        if dash and dash.lower() != "solid":
            attributes["stroke-dasharray"] = _DASH_ARRAYS.get(dash.lower(), dash)
        ET.SubElement(group, _tag("rect"), attributes)
        if item.label:
            label_box = Box(
                item.box.x + 0.08,
                item.box.y + 0.02,
                max(0.1, item.box.width - 0.16),
                min(0.35, item.box.height),
            )
            _text(
                group,
                label_box,
                item.label,
                item.style,
                default_color="#52687A",
                default_size=11.0,
                align="left",
                points_to_units=points_to_units,
            )

    def _shape(self, root: ET.Element, item: SceneShape, points_to_units: float) -> None:
        group = _semantic_group(root, item.semantic_id, item.role)
        if abs(item.rotation) > 1e-9:
            group.set(
                "transform",
                (
                    f"rotate({_num(item.rotation)} "
                    f"{_num(item.box.center.x)} {_num(item.box.center.y)})"
                ),
            )
        style = _shape_style(item.style, points_to_units)
        box = item.box
        shape = item.shape
        if shape == "ellipse":
            ET.SubElement(
                group,
                _tag("ellipse"),
                {
                    "cx": _num(box.center.x),
                    "cy": _num(box.center.y),
                    "rx": _num(box.width / 2),
                    "ry": _num(box.height / 2),
                    **style,
                },
            )
        elif shape in {"diamond", "hexagon", "parallelogram", "custom"}:
            points = item.points or _preset_points(shape, box)
            ET.SubElement(
                group,
                _tag("polygon"),
                {
                    "points": " ".join(f"{_num(point.x)},{_num(point.y)}" for point in points),
                    **style,
                },
            )
        elif shape == "cylinder":
            self._cylinder(group, box, style)
        else:
            radius = 0.0
            if shape == "stadium":
                radius = box.height / 2
            elif shape == "rounded_rectangle":
                radius = min(box.width, box.height) * 0.18
            attributes = {**_box_attributes(box), **style}
            if radius:
                attributes["rx"] = _num(radius)
            ET.SubElement(group, _tag("rect"), attributes)
            if shape == "subprocess":
                inset = min(box.width * 0.08, 0.18)
                for x in (box.x + inset, box.x + box.width - inset):
                    ET.SubElement(
                        group,
                        _tag("line"),
                        {
                            "x1": _num(x),
                            "y1": _num(box.y),
                            "x2": _num(x),
                            "y2": _num(box.y + box.height),
                            "stroke": style["stroke"],
                            "stroke-width": style["stroke-width"],
                        },
                    )
        if item.text:
            _text(
                group,
                box,
                item.text,
                item.style,
                default_color="#16324F",
                default_size=15.0,
                points_to_units=points_to_units,
            )

    @staticmethod
    def _cylinder(group: ET.Element, box: Box, style: dict[str, str]) -> None:
        radius_y = min(box.height * 0.14, box.width * 0.11)
        body_y = box.y + radius_y
        body_height = max(0.001, box.height - 2 * radius_y)
        ET.SubElement(
            group,
            _tag("rect"),
            {
                "x": _num(box.x),
                "y": _num(body_y),
                "width": _num(box.width),
                "height": _num(body_height),
                **style,
            },
        )
        for y in (body_y, body_y + body_height):
            ellipse_style = dict(style)
            if y > body_y:
                ellipse_style["fill"] = "none"
            ET.SubElement(
                group,
                _tag("ellipse"),
                {
                    "cx": _num(box.center.x),
                    "cy": _num(y),
                    "rx": _num(box.width / 2),
                    "ry": _num(radius_y),
                    **ellipse_style,
                },
            )

    def _connector(
        self,
        root: ET.Element,
        defs: ET.Element,
        item: SceneConnector,
        index: int,
        points_to_units: float,
    ) -> None:
        if len(item.points) < 2:
            return
        group = _semantic_group(root, item.semantic_id, item.role)
        line_color, line_opacity = _color(item.style.line or "#536273", item.style.opacity)
        attributes = {
            "points": " ".join(f"{_num(point.x)},{_num(point.y)}" for point in item.points),
            "fill": "none",
            "stroke": line_color,
            "stroke-width": _stroke_width(item.style, points_to_units),
            "stroke-linecap": "square",
            "stroke-linejoin": "miter",
        }
        if line_opacity < 1:
            attributes["stroke-opacity"] = _num(line_opacity)
        if item.style.dash and item.style.dash.lower() != "solid":
            attributes["stroke-dasharray"] = _DASH_ARRAYS.get(
                item.style.dash.lower(), item.style.dash
            )
        if item.start_marker:
            marker_id = f"marker-{index}-start"
            _marker(defs, marker_id, item.start_marker, line_color, start=True)
            attributes["marker-start"] = f"url(#{marker_id})"
        if item.directed and item.end_marker:
            marker_id = f"marker-{index}-end"
            _marker(defs, marker_id, item.end_marker, line_color)
            attributes["marker-end"] = f"url(#{marker_id})"
        ET.SubElement(group, _tag("polyline"), attributes)
        if item.label:
            point = _label_point(item)
            label_width = max(0.42, min(3.0, _text_columns(item.label) * 0.09 + 0.18))
            label_box = Box(point.x - label_width / 2, point.y - 0.18, label_width, 0.36)
            fill = item.style.label_fill
            if fill and normalize_color(fill) not in {"none", "transparent", "#00000000"}:
                fill_color, fill_opacity = _color(fill, item.style.opacity)
                fill_attributes = {
                    **_box_attributes(label_box),
                    "fill": fill_color,
                    "stroke": "none",
                }
                if fill_opacity < 1:
                    fill_attributes["fill-opacity"] = _num(fill_opacity)
                ET.SubElement(group, _tag("rect"), fill_attributes)
            _text(
                group,
                label_box,
                item.label,
                item.style,
                default_color=line_color,
                default_size=11.0,
                points_to_units=points_to_units,
            )

    @staticmethod
    def _standalone_text(root: ET.Element, item: SceneText, points_to_units: float) -> None:
        group = _semantic_group(root, item.semantic_id, item.role)
        if item.role == "edge.label":
            fill = item.style.label_fill or item.style.fill
            if fill and normalize_color(fill) not in {"none", "transparent", "#00000000"}:
                color, opacity = _color(fill, item.style.opacity)
                attributes = {**_box_attributes(item.box), "fill": color, "stroke": "none"}
                if opacity < 1:
                    attributes["fill-opacity"] = _num(opacity)
                ET.SubElement(group, _tag("rect"), attributes)
        _text(
            group,
            item.box,
            item.text,
            item.style,
            default_color="#16324F",
            default_size=12.0,
            align=item.align,
            points_to_units=points_to_units,
            rotation=item.rotation,
        )


def _semantic_group(root: ET.Element, semantic_id: str, role: str) -> ET.Element:
    return ET.SubElement(
        root,
        _tag("g"),
        {
            "data-semantic-id": semantic_id,
            "data-role": role,
        },
    )


def _text(
    parent: ET.Element,
    box: Box,
    value: str,
    style: ElementStyle,
    *,
    default_color: str,
    default_size: float,
    points_to_units: float,
    align: str = "center",
    rotation: float = 0.0,
) -> None:
    lines = re.split(r"(?:\r?\n|<br\s*/?>)", value, flags=re.IGNORECASE) or [""]
    if isinstance(style.font_size, FontSize):
        font_size = (
            style.font_size.resolve() if style.font_size.is_absolute else style.font_size.value
        )
    else:
        font_size = float(style.font_size or default_size)
    line_height = font_size * 1.2 * points_to_units
    total_height = line_height * max(1, len(lines))
    first_y = box.y + box.height / 2 - total_height / 2 + line_height * 0.82
    if align == "left":
        x = box.x + min(box.width * 0.08, 0.12 if box.width < 10 else 8)
        anchor = "start"
    elif align == "right":
        x = box.x + box.width - min(box.width * 0.08, 0.12 if box.width < 10 else 8)
        anchor = "end"
    else:
        x = box.center.x
        anchor = "middle"
    color, opacity = _color(style.text or default_color, style.opacity)
    attributes = {
        "x": _num(x),
        "y": _num(first_y),
        "fill": color,
        "font-family": _svg_font_family(style.font_family),
        "font-size": _num(font_size * points_to_units),
        "text-anchor": anchor,
    }
    if style.bold:
        attributes["font-weight"] = "700"
    if style.italic:
        attributes["font-style"] = "italic"
    if opacity < 1:
        attributes["fill-opacity"] = _num(opacity)
    if abs(rotation) > 1e-9:
        attributes["transform"] = (
            f"rotate({_num(rotation)} {_num(box.center.x)} {_num(box.center.y)})"
        )
    text_element = ET.SubElement(parent, _tag("text"), attributes)
    for index, line in enumerate(lines):
        tspan = ET.SubElement(
            text_element,
            _tag("tspan"),
            {
                "x": _num(x),
                "y": _num(first_y + index * line_height),
            },
        )
        tspan.text = line


def _shape_style(style: ElementStyle, points_to_units: float) -> dict[str, str]:
    fill, fill_opacity = _color(style.fill or "#EAF2FF", style.opacity)
    stroke, stroke_opacity = _color(style.line or "#3167A5", style.opacity)
    result = {
        "fill": fill,
        "stroke": stroke,
        "stroke-width": _stroke_width(style, points_to_units),
        "stroke-linejoin": "miter",
    }
    if fill_opacity < 1:
        result["fill-opacity"] = _num(fill_opacity)
    if stroke_opacity < 1:
        result["stroke-opacity"] = _num(stroke_opacity)
    if style.dash and style.dash.lower() != "solid":
        result["stroke-dasharray"] = _DASH_ARRAYS.get(style.dash.lower(), style.dash)
    return result


def _preset_points(shape: str, box: Box) -> list[Point]:
    x, y, width, height = box.x, box.y, box.width, box.height
    if shape == "diamond":
        return [
            Point(x + width / 2, y),
            Point(x + width, y + height / 2),
            Point(x + width / 2, y + height),
            Point(x, y + height / 2),
        ]
    if shape == "hexagon":
        inset = width * 0.22
        return [
            Point(x + inset, y),
            Point(x + width - inset, y),
            Point(x + width, y + height / 2),
            Point(x + width - inset, y + height),
            Point(x + inset, y + height),
            Point(x, y + height / 2),
        ]
    if shape == "parallelogram":
        inset = width * 0.16
        return [
            Point(x + inset, y),
            Point(x + width, y),
            Point(x + width - inset, y + height),
            Point(x, y + height),
        ]
    return [
        Point(x, y),
        Point(x + width, y),
        Point(x + width, y + height),
        Point(x, y + height),
    ]


def _marker(
    defs: ET.Element,
    marker_id: str,
    marker: str,
    color: str,
    *,
    start: bool = False,
) -> None:
    normalized = marker.lower()
    marker_element = ET.SubElement(
        defs,
        _tag("marker"),
        {
            "id": marker_id,
            "viewBox": "0 0 10 10",
            "refX": "1.5" if start else "8.5",
            "refY": "5",
            "markerWidth": "8",
            "markerHeight": "8",
            "orient": "auto-start-reverse",
            "markerUnits": "strokeWidth",
        },
    )
    if normalized in {"diamond"}:
        ET.SubElement(
            marker_element,
            _tag("path"),
            {"d": "M 1 5 L 5 1 L 9 5 L 5 9 Z", "fill": color, "stroke": color},
        )
    elif normalized in {"oval", "circle"} or normalized.startswith("cardinality:"):
        ET.SubElement(
            marker_element,
            _tag("circle"),
            {"cx": "5", "cy": "5", "r": "3.5", "fill": color, "stroke": color},
        )
    else:
        ET.SubElement(
            marker_element,
            _tag("path"),
            {"d": "M 1 1 L 9 5 L 1 9 Z", "fill": color, "stroke": color},
        )


def _label_point(item: SceneConnector) -> Point:
    raw = item.metadata.get("label_point")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return Point(float(raw[0]), float(raw[1]))
    pairs = zip(item.points, item.points[1:], strict=False)
    total = sum(hypot(b.x - a.x, b.y - a.y) for a, b in pairs)
    remaining = total / 2
    for start, end in zip(item.points, item.points[1:], strict=False):
        length = hypot(end.x - start.x, end.y - start.y)
        if remaining <= length and length:
            ratio = remaining / length
            return Point(
                start.x + (end.x - start.x) * ratio,
                start.y + (end.y - start.y) * ratio,
            )
        remaining -= length
    return item.points[-1]


def _resolve_dimensions(
    natural_width: int,
    natural_height: int,
    width_px: int | None,
    height_px: int | None,
) -> tuple[int, int]:
    if width_px is not None and width_px <= 0:
        raise ValueError("width_px must be greater than zero")
    if height_px is not None and height_px <= 0:
        raise ValueError("height_px must be greater than zero")
    if width_px is None and height_px is None:
        return natural_width, natural_height
    if width_px is None:
        assert height_px is not None
        return max(1, round(natural_width * height_px / natural_height)), height_px
    if height_px is None:
        return width_px, max(1, round(natural_height * width_px / natural_width))
    return width_px, height_px


def _box_attributes(box: Box) -> dict[str, str]:
    return {
        "x": _num(box.x),
        "y": _num(box.y),
        "width": _num(box.width),
        "height": _num(box.height),
    }


def _color(value: str, opacity: float | None = None) -> tuple[str, float]:
    normalized = normalize_color(value)
    normalized = _THEME_COLORS.get(normalized, normalized)
    if normalized in {"none", "transparent"}:
        return "none", 0.0
    match = re.fullmatch(r"#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", normalized)
    if not match:
        raise ValueError(f"Expected RGB, RGBA, or theme color, got {value!r}")
    alpha = int(match.group(2), 16) / 255 if match.group(2) else 1.0
    if opacity is not None:
        alpha *= max(0.0, min(1.0, opacity))
    return f"#{match.group(1).upper()}", alpha


def _stroke_width(style: ElementStyle, points_to_units: float) -> str:
    return _num((style.line_width or 1.4) * points_to_units)


def _text_columns(value: str) -> int:
    return max(len(line) for line in re.split(r"(?:\r?\n|<br\s*/?>)", value))


def _svg_font_family(value: str | None) -> str:
    if value is None or value.strip().lower() in {"aptos", "arial", "helvetica"}:
        return "sans-serif"
    if value.strip().lower() in {"yu gothic", "yugothic", "游ゴシック"}:
        return "'Yu Gothic', YuGothic, sans-serif"
    return value


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") or "0"


def _tag(name: str) -> str:
    return f"{{{_SVG_NS}}}{name}"
