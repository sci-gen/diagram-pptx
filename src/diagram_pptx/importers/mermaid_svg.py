"""Import SVG emitted by Mermaid CLI into editable DrawingScene primitives."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from html import unescape
from math import atan2, ceil, cos, degrees, hypot, pi, radians, sin, sqrt
from unicodedata import east_asian_width

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

_NUMBER_RE = re.compile(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_PATH_TOKEN_RE = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)")
_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]+)\}")
_INHERITED_STYLE_NAMES = frozenset(
    {
        "fill",
        "fill-opacity",
        "stroke",
        "stroke-opacity",
        "stroke-width",
        "stroke-dasharray",
        "color",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "text-anchor",
        "dominant-baseline",
        "visibility",
        "opacity",
    }
)


@dataclass(frozen=True, slots=True)
class _Affine:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def apply(self, point: Point) -> Point:
        return Point(
            self.a * point.x + self.c * point.y + self.e,
            self.b * point.x + self.d * point.y + self.f,
        )

    def then(self, other: _Affine) -> _Affine:
        return _Affine(
            a=other.a * self.a + other.c * self.b,
            b=other.b * self.a + other.d * self.b,
            c=other.a * self.c + other.c * self.d,
            d=other.b * self.c + other.d * self.d,
            e=other.a * self.e + other.c * self.f + other.e,
            f=other.b * self.e + other.d * self.f + other.f,
        )


@dataclass(frozen=True, slots=True)
class _CssRule:
    required_classes: frozenset[str]
    target_tag: str | None
    declarations: dict[str, str]
    specificity: tuple[int, int, int]
    order: int


@dataclass(slots=True)
class _Stylesheet:
    root: dict[str, str]
    rules: list[_CssRule]


def import_mermaid_svg(svg: str | bytes, *, kind: str) -> DrawingScene:
    """Parse safe visible Mermaid SVG primitives; external resources are ignored."""

    data = svg.decode("utf-8") if isinstance(svg, bytes) else svg
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid Mermaid SVG: {exc}") from exc
    if _local(root.tag) != "svg":
        raise ValueError(f"Expected SVG root, got {_local(root.tag)!r}")

    css = _parse_css(root)
    paint_servers = _parse_paint_servers(root)
    view_box = _numbers(root.get("viewBox", ""))
    if len(view_box) >= 4:
        min_x, min_y, width, height = view_box[:4]
    else:
        min_x = min_y = 0.0
        width = _length(root.get("width"), 100.0)
        height = _length(root.get("height"), 100.0)
    root_transform = _Affine(e=-min_x, f=-min_y)
    scene = DrawingScene(
        kind=kind,
        width=width,
        height=height,
        metadata={
            "layout_engine": "official-mermaid-svg",
            "coordinate_units": "svg_px",
            "svg_role": root.get("aria-roledescription"),
        },
    )
    counter = [0]
    for child in root:
        _walk(
            child,
            scene,
            css=css,
            paint_servers=paint_servers,
            transform=root_transform,
            inherited_id=None,
            inherited_classes=set(),
            inherited_style={},
            counter=counter,
        )
    _mark_actor_composites(scene)
    _mark_state_pseudostate_composites(scene)
    _coalesce_node_labels(scene)
    _infer_connector_endpoints(scene)
    _snap_connector_ends(scene)
    _improve_sequence_self_messages(scene)
    _improve_radar_typography(scene)
    scene.recompute_extents()
    return scene


def _improve_radar_typography(scene: DrawingScene) -> None:
    """Keep Mermaid radar labels readable after fitting the chart to a slide."""

    if scene.kind != "radar":
        return
    graticules = [
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and "radarGraticule" in item.classes
    ]
    if graticules:
        outer = max(graticules, key=lambda item: item.box.width * item.box.height)
        center = outer.box.center
        geometry_scale = 0.86
        for item in scene.elements:
            if isinstance(item, SceneShape) and not item.classes.isdisjoint(
                {"radarGraticule", "radarCurve-0", "radarCurve-1"}
            ):
                item.box = _scale_box_around(item.box, center, geometry_scale)
                if item.points:
                    item.points = [
                        _scale_point_around(point, center, geometry_scale) for point in item.points
                    ]
                    item.box = _box_for_points(item.points)
            elif isinstance(item, SceneConnector) and "radarAxisLine" in item.classes:
                item.points = [
                    _scale_point_around(point, center, geometry_scale) for point in item.points
                ]
            elif isinstance(item, SceneText) and "radarAxisLabel" in item.classes:
                label_center = _scale_point_around(item.box.center, center, 0.91)
                item.box = Box(
                    label_center.x - item.box.width / 2,
                    label_center.y - item.box.height / 2,
                    item.box.width,
                    item.box.height,
                )
    target_sizes = {
        "radarAxisLabel": 30.0,
        "radarLegendText": 22.0,
        "radarTitle": 26.0,
    }
    for item in scene.elements:
        if not isinstance(item, SceneText):
            continue
        target_size = next(
            (size for class_name, size in target_sizes.items() if class_name in item.classes),
            None,
        )
        if target_size is None:
            continue
        current_size = item.style.font_size or 14.0
        if current_size >= target_size:
            continue
        scale = target_size / current_size
        old_box = item.box
        width = old_box.width * scale
        height = old_box.height * scale
        if item.align == "left":
            left = old_box.x
        elif item.align == "right":
            left = old_box.x + old_box.width - width
        else:
            left = old_box.center.x - width / 2
        item.box = Box(
            left,
            old_box.center.y - height / 2,
            width,
            height,
        )
        item.style.font_size = target_size


def _scale_point_around(point: Point, center: Point, scale: float) -> Point:
    return Point(
        center.x + (point.x - center.x) * scale,
        center.y + (point.y - center.y) * scale,
    )


def _scale_box_around(box: Box, center: Point, scale: float) -> Box:
    top_left = _scale_point_around(Point(box.x, box.y), center, scale)
    return Box(
        top_left.x,
        top_left.y,
        box.width * scale,
        box.height * scale,
    )


def _walk(
    element: ET.Element,
    scene: DrawingScene,
    *,
    css: _Stylesheet,
    paint_servers: dict[str, str],
    transform: _Affine,
    inherited_id: str | None,
    inherited_classes: set[str],
    inherited_style: dict[str, str],
    counter: list[int],
) -> None:
    tag = _local(element.tag)
    if tag in {
        "defs",
        "style",
        "script",
        "marker",
        "image",
        "use",
        "a",
        "title",
        "desc",
        "clipPath",
        "mask",
        "pattern",
        "symbol",
    }:
        return
    classes = inherited_classes | set(element.get("class", "").split())
    declarations = _element_declarations(element, classes, css, inherited_style)
    if declarations.get("display", "").lower() == "none" or declarations.get(
        "visibility", ""
    ).lower() in {"hidden", "collapse"}:
        return
    semantic_id = _semantic_id(
        element.get("id") or element.get("data-id") or inherited_id,
        classes,
    )
    css_transform = declarations.get("transform")
    if css_transform and css_transform.strip().lower() != "none":
        local_transform = _transform_with_origin(
            css_transform,
            declarations.get("transform-origin") or element.get("transform-origin"),
        )
    else:
        local_transform = _parse_transform(element.get("transform", ""))
    if tag == "svg":
        local_transform = _svg_viewport_transform(element).then(local_transform)
    current_transform = local_transform.then(transform)
    style = _element_style(
        element,
        classes,
        css,
        paint_servers,
        inherited_style,
    )
    element_id = f"svg-{counter[0]}"
    counter[0] += 1
    role = _role(classes, tag)

    if tag == "foreignObject":
        box = _transformed_box(
            Box(
                _length(element.get("x"), 0.0),
                _length(element.get("y"), 0.0),
                _length(element.get("width"), 1.0),
                _length(element.get("height"), 0.4),
            ),
            current_transform,
        )
        text = _clean_text(" ".join(element.itertext()))
        if text:
            style = _foreign_object_text_style(
                element,
                classes,
                css,
                paint_servers,
                inherited_style,
            )
            if style.font_size is None:
                style.font_size = 16.0
            text_role = "edge.label" if "edgeLabel" in classes else "text.default"
            if text_role == "edge.label":
                # The label background belongs to the XHTML child in Mermaid
                # SVG, not to the foreignObject itself.  Let the semantic
                # edge-label theme provide the PowerPoint fill.
                style.fill = None
            else:
                style.text = style.text or style.fill
                style.fill = None
            scene.add(
                SceneText(
                    id=element_id,
                    semantic_id=semantic_id or element_id,
                    role=text_role,
                    classes=classes,
                    style=style,
                    z_index=_svg_order(element_id),
                    box=box,
                    text=text,
                )
            )
        return
    if tag == "rect":
        raw_width = _length(element.get("width"), 0.0)
        raw_height = _length(element.get("height"), 0.0)
        # Mermaid emits empty <rect/> elements as label-layout helpers.  They
        # are not visible SVG geometry and must not become tiny PowerPoint
        # rectangles.
        if raw_width <= 0 or raw_height <= 0:
            return
        box, rotation = _transformed_primitive_box(
            Box(
                _length(element.get("x"), 0.0),
                _length(element.get("y"), 0.0),
                raw_width,
                raw_height,
            ),
            current_transform,
        )
        if box.width > 0 and box.height > 0 and not _invisible(style):
            rx = _length(element.get("rx"), 0.0)
            ry = _length(element.get("ry"), rx)
            shape = "rounded_rectangle" if rx > 0 or ry > 0 else "rectangle"
            added = _add_shape(
                scene,
                element_id,
                semantic_id,
                role,
                classes,
                style,
                box,
                shape,
            )
            if isinstance(added, SceneShape) and shape == "rounded_rectangle":
                radius = max(rx, ry)
                added.metadata["corner_radius_ratio"] = min(
                    0.5,
                    radius / max(min(raw_width, raw_height), 1e-9),
                )
            if isinstance(added, SceneShape):
                added.rotation = rotation
        return
    if tag in {"circle", "ellipse"}:
        cx = _length(element.get("cx"), 0.0)
        cy = _length(element.get("cy"), 0.0)
        rx = _length(element.get("r" if tag == "circle" else "rx"), 0.0)
        ry = _length(element.get("r" if tag == "circle" else "ry"), rx)
        box, rotation = _transformed_primitive_box(
            Box(cx - rx, cy - ry, 2 * rx, 2 * ry),
            current_transform,
        )
        if box.width > 0 and box.height > 0 and not _invisible(style):
            added = _add_shape(
                scene,
                element_id,
                semantic_id,
                role,
                classes,
                style,
                box,
                "ellipse",
            )
            if isinstance(added, SceneShape):
                added.rotation = rotation
        return
    if tag in {"polygon", "polyline"}:
        points = _point_pairs(element.get("points", ""), current_transform)
        if len(points) >= 2:
            connector_role = role.startswith("edge.") or role == "sequence.message"
            if tag == "polyline" or (
                connector_role and style.fill in {None, "none", "transparent", "#00000000"}
            ):
                _add_connector(
                    scene, element_id, semantic_id, role, classes, style, points, element
                )
            else:
                box = _box_for_points(points)
                shape = "diamond" if len(points) == 4 and _looks_like_diamond(points) else "custom"
                _add_shape(
                    scene,
                    element_id,
                    semantic_id,
                    role,
                    classes,
                    style,
                    box,
                    shape,
                    points=points,
                )
        return
    if tag == "line":
        points = [
            current_transform.apply(
                Point(
                    _length(element.get("x1"), 0.0),
                    _length(element.get("y1"), 0.0),
                )
            ),
            current_transform.apply(
                Point(
                    _length(element.get("x2"), 0.0),
                    _length(element.get("y2"), 0.0),
                )
            ),
        ]
        _add_connector(scene, element_id, semantic_id, role, classes, style, points, element)
        return
    if tag == "path":
        points = _path_points(element.get("d", ""), current_transform)
        if len(points) >= 2:
            fill = (style.fill or element.get("fill") or "none").lower()
            declared_fill = declarations.get("fill", "").strip().lower()
            if (
                declared_fill in {"none", "transparent", "#00000000"}
                and style.line is None
                and not element.get("marker-start")
                and not element.get("marker-end")
            ):
                return
            connector_role = role.startswith("edge.") or role == "sequence.message"
            if connector_role or (
                fill in {"none", "transparent", "#00000000"} and "node" not in classes
            ):
                _add_connector(
                    scene, element_id, semantic_id, role, classes, style, points, element
                )
            else:
                shape = (
                    "cylinder"
                    if "outer-path" in classes and re.search(r"[Aa]", element.get("d", ""))
                    else "custom"
                )
                _add_shape(
                    scene,
                    element_id,
                    semantic_id,
                    role,
                    classes,
                    style,
                    _box_for_points(points),
                    shape,
                    points=points,
                )
        return
    if tag == "text":
        text = _svg_text_content(element)
        if text:
            font_size = style.font_size or _length(element.get("font-size"), 14.0)
            x, y = _text_position(element, font_size)
            width = max(font_size * 0.5, _estimated_text_width(text, font_size))
            height = max(1.0, font_size * 1.2 * max(1, len(text.splitlines())))
            anchor = declarations.get("text-anchor", "start").lower()
            align = {
                "start": "left",
                "middle": "center",
                "end": "right",
            }.get(anchor, "left")
            local_left = x
            if anchor == "middle":
                local_left -= width / 2
            elif anchor == "end":
                local_left -= width
            baseline = declarations.get("dominant-baseline", "auto").lower()
            if baseline in {"middle", "central"}:
                local_top = y - height / 2
            elif baseline in {"hanging", "text-before-edge"}:
                local_top = y
            else:
                local_top = y - height * 0.82
            local_center = Point(local_left + width / 2, local_top + height / 2)
            center = current_transform.apply(local_center)
            scale_x = hypot(current_transform.a, current_transform.b)
            scale_y = hypot(current_transform.c, current_transform.d)
            box = Box(
                center.x - width * scale_x / 2,
                center.y - height * scale_y / 2,
                width * scale_x,
                height * scale_y,
            )
            style.text = style.fill or style.text
            style.fill = None
            scene.add(
                SceneText(
                    id=element_id,
                    semantic_id=semantic_id or element_id,
                    role="text.default",
                    classes=classes,
                    style=style,
                    z_index=_svg_order(element_id),
                    box=box,
                    text=text,
                    align=align,
                    rotation=degrees(atan2(current_transform.b, current_transform.a)),
                )
            )
        return

    child_id = element.get("id") or inherited_id
    child_style = {
        name: value for name, value in declarations.items() if name in _INHERITED_STYLE_NAMES
    }
    for child in element:
        _walk(
            child,
            scene,
            css=css,
            paint_servers=paint_servers,
            transform=current_transform,
            inherited_id=child_id,
            inherited_classes=classes,
            inherited_style=child_style,
            counter=counter,
        )


def _coalesce_node_labels(scene: DrawingScene) -> None:
    """Put simple node labels in their native PowerPoint shape.

    Mermaid SVG represents geometry and labels separately.  For flow, state,
    and Kanban nodes a single label can safely become the shape's own text
    frame, which is more editable and prevents a redundant textbox from
    drifting during group scaling. Structured diagrams keep their independent
    compartment text.
    """

    if scene.kind not in {"flowchart", "kanban", "state"}:
        return
    shapes_by_id: dict[str, list[SceneShape]] = {}
    for element in scene.elements:
        if isinstance(element, SceneShape) and element.role.startswith("node."):
            shapes_by_id.setdefault(element.semantic_id, []).append(element)

    consumed: set[int] = set()
    for text in (item for item in scene.elements if isinstance(item, SceneText)):
        candidates = shapes_by_id.get(text.semantic_id, [])
        center = text.box.center
        containing = [
            shape
            for shape in candidates
            if shape.box.x <= center.x <= shape.box.x + shape.box.width
            and shape.box.y <= center.y <= shape.box.y + shape.box.height
        ]
        if not containing:
            continue
        # The renderer's primary semantic shape is the last geometry emitted
        # for an ID, so attach the label to that same shape.
        shape = containing[-1]
        if shape.text:
            continue
        shape.text = text.text
        shape.style = shape.style.merged(text.style)
        consumed.add(id(text))
    if consumed:
        scene.elements = [item for item in scene.elements if id(item) not in consumed]


def _improve_sequence_self_messages(scene: DrawingScene) -> None:
    """Keep official Mermaid self-message arrows readable after PPT scaling.

    Mermaid emits compact loops whose sequence number sits on the start point.
    In PowerPoint the separate native line segments and text boxes can then
    obscure the arrow.  Preserve the direction and row while enforcing a
    readable loop size and moving only the associated label/number.
    """

    if scene.kind != "sequence":
        return
    message_texts = [
        item
        for item in scene.elements
        if isinstance(item, SceneText) and "messageText" in item.classes
    ]
    sequence_numbers = [
        item
        for item in scene.elements
        if isinstance(item, SceneText) and "sequenceNumber" in item.classes
    ]
    for connector in (
        item
        for item in scene.elements
        if isinstance(item, SceneConnector)
        and item.role == "sequence.message"
        and item.source_id
        and item.source_id == item.target_id
        and len(item.points) >= 2
    ):
        start = connector.points[0]
        end = connector.points[-1]
        interior = connector.points[1:-1]
        interior_x = sum(point.x for point in interior) / len(interior) if interior else start.x
        direction = 1 if interior_x >= start.x else -1
        loop_width = max(80.0, max(abs(point.x - start.x) for point in connector.points))
        end_y = end.y
        if abs(end_y - start.y) < 30.0:
            end_y = start.y + (30.0 if end_y >= start.y else -30.0)
        outer_x = start.x + direction * loop_width
        connector.points = [
            Point(start.x, start.y),
            Point(outer_x, start.y),
            Point(outer_x, end_y),
            Point(end.x, end_y),
        ]
        connector.metadata["readable_self_message"] = True

        label_candidates = [
            item
            for item in message_texts
            if 0 <= start.y - item.box.center.y <= 65 and abs(item.box.center.x - start.x) <= 120
        ]
        if label_candidates:
            label = min(
                label_candidates,
                key=lambda item: (
                    abs(start.y - item.box.center.y - 28),
                    abs(item.box.center.x - start.x),
                ),
            )
            desired_center_x = start.x + direction * loop_width / 2
            label.box = Box(
                label.box.x + desired_center_x - label.box.center.x,
                label.box.y,
                label.box.width,
                label.box.height,
            )

        number_candidates = [
            item
            for item in sequence_numbers
            if abs(item.box.center.y - start.y) <= 20 and abs(item.box.center.x - start.x) <= 30
        ]
        if number_candidates:
            number = min(
                number_candidates,
                key=lambda item: abs(item.box.center.y - start.y),
            )
            desired_center_x = start.x - direction * 14
            desired_center_y = start.y - 12
            number.box = Box(
                number.box.x + desired_center_x - number.box.center.x,
                number.box.y + desired_center_y - number.box.center.y,
                number.box.width,
                number.box.height,
            )


def _mark_actor_composites(scene: DrawingScene) -> None:
    """Mark each Mermaid stick figure for nested PowerPoint grouping."""

    if scene.kind != "sequence":
        return
    for position in ("actor-top", "actor-bottom"):
        anchors = sorted(
            (
                item
                for item in scene.elements
                if isinstance(item, SceneShape)
                and "actor-man" in item.classes
                and position in item.classes
                and item.shape == "ellipse"
            ),
            key=lambda item: item.box.center.x,
        )
        if not anchors:
            continue
        actor_parts = [
            item
            for item in scene.elements
            if "actor-man" in item.classes and position in item.classes
        ]
        for part in actor_parts:
            center_x = _element_center_x(part)
            anchor_index, _ = min(
                enumerate(anchors),
                key=lambda item: abs(item[1].box.center.x - center_x),
            )
            anchor = anchors[anchor_index]
            labels = [
                item
                for item in actor_parts
                if isinstance(item, SceneText) and abs(item.box.center.x - anchor.box.center.x) < 50
            ]
            label = (
                min(
                    labels,
                    key=lambda item: abs(item.box.center.y - anchor.box.center.y),
                ).text
                if labels
                else f"actor-{anchor_index}"
            )
            part.metadata["composite_group"] = f"sequence-actor:{position}:{anchor_index}"
            part.metadata["composite_group_name"] = f"diagram:sequence:actor:{label}:{position}"


def _mark_state_pseudostate_composites(scene: DrawingScene) -> None:
    """Group the concentric native parts of Mermaid state end markers."""

    if scene.kind != "state":
        return
    shapes_by_id: dict[str, list[SceneShape]] = {}
    for item in scene.elements:
        if isinstance(item, SceneShape):
            shapes_by_id.setdefault(item.semantic_id, []).append(item)
    for semantic_id, shapes in shapes_by_id.items():
        if len(shapes) < 2 or not semantic_id.startswith("root_"):
            continue
        for shape in shapes:
            shape.metadata["composite_group"] = f"state-pseudostate:{semantic_id}"
            shape.metadata["composite_group_name"] = f"diagram:state:pseudostate:{semantic_id}"


def _element_center_x(element: SceneShape | SceneConnector | SceneText) -> float:
    if isinstance(element, (SceneShape, SceneText)):
        return element.box.center.x
    return sum(point.x for point in element.points) / max(len(element.points), 1)


def _snap_connector_ends(scene: DrawingScene) -> None:
    """Extend Mermaid marker-margin endpoints to both shape boundaries."""

    shapes_by_id: dict[str, list[SceneShape]] = {}
    for element in scene.elements:
        if isinstance(element, SceneShape):
            shapes_by_id.setdefault(element.semantic_id, []).append(element)
    for connector in (
        item
        for item in scene.elements
        if isinstance(item, SceneConnector) and len(item.points) >= 2
    ):
        source_candidates = shapes_by_id.get(connector.source_id or "", [])
        if source_candidates:
            source_shape = max(
                source_candidates,
                key=lambda item: item.box.width * item.box.height,
            )
            intersection = _segment_shape_intersection(
                connector.points[0],
                source_shape.box.center,
                source_shape,
            )
            if intersection is not None:
                connector.points[0] = intersection

        target_candidates = shapes_by_id.get(connector.target_id or "", [])
        if target_candidates:
            target_shape = max(
                target_candidates,
                key=lambda item: item.box.width * item.box.height,
            )
            intersection = _segment_shape_intersection(
                connector.points[-1],
                target_shape.box.center,
                target_shape,
            )
            if intersection is not None:
                connector.points[-1] = intersection


def _infer_connector_endpoints(scene: DrawingScene) -> None:
    """Recover Mermaid endpoint IDs when a diagram family omits data-from/to."""

    primary_shapes: dict[str, SceneShape] = {}
    for shape in (item for item in scene.elements if isinstance(item, SceneShape)):
        current = primary_shapes.get(shape.semantic_id)
        if current is None or shape.box.width * shape.box.height > (
            current.box.width * current.box.height
        ):
            primary_shapes[shape.semantic_id] = shape
    if not primary_shapes:
        return

    for connector in (
        item
        for item in scene.elements
        if isinstance(item, SceneConnector) and len(item.points) >= 2
    ):
        if connector.role != "edge.default":
            continue
        if {"actor-man", "actor-line"} & connector.classes:
            continue
        if not (
            connector.start_marker
            or connector.end_marker
            or {"relation", "transition", "flowchart-link"} & connector.classes
        ):
            continue
        if connector.source_id is None:
            connector.source_id = min(
                primary_shapes,
                key=lambda item: _distance_to_box(
                    connector.points[0],
                    primary_shapes[item].box,
                ),
            )
        if connector.target_id is None:
            choices = [item for item in primary_shapes if item != connector.source_id] or list(
                primary_shapes
            )
            connector.target_id = min(
                choices,
                key=lambda item: _distance_to_box(
                    connector.points[-1],
                    primary_shapes[item].box,
                ),
            )


def _distance_to_box(point: Point, box: Box) -> float:
    dx = max(box.x - point.x, 0.0, point.x - (box.x + box.width))
    dy = max(box.y - point.y, 0.0, point.y - (box.y + box.height))
    return (dx * dx + dy * dy) ** 0.5


def _segment_shape_intersection(
    start: Point,
    end: Point,
    shape: SceneShape,
) -> Point | None:
    boundary = list(shape.points)
    if shape.shape == "diamond" and len(boundary) >= 3:
        return _nearest_segment_intersection(start, end, boundary)

    box = shape.box
    boundary = [
        Point(box.x, box.y),
        Point(box.x + box.width, box.y),
        Point(box.x + box.width, box.y + box.height),
        Point(box.x, box.y + box.height),
    ]
    return _nearest_segment_intersection(start, end, boundary)


def _nearest_segment_intersection(
    start: Point,
    end: Point,
    boundary: list[Point],
) -> Point | None:
    direction_x = end.x - start.x
    direction_y = end.y - start.y
    candidates: list[tuple[float, Point]] = []
    for first, second in zip(boundary, boundary[1:] + boundary[:1], strict=True):
        edge_x = second.x - first.x
        edge_y = second.y - first.y
        denominator = direction_x * edge_y - direction_y * edge_x
        if abs(denominator) < 1e-9:
            continue
        offset_x = first.x - start.x
        offset_y = first.y - start.y
        along_ray = (offset_x * edge_y - offset_y * edge_x) / denominator
        along_edge = (offset_x * direction_y - offset_y * direction_x) / denominator
        if -1e-9 <= along_ray <= 1.0 + 1e-9 and -1e-9 <= along_edge <= 1.0 + 1e-9:
            candidates.append(
                (
                    along_ray,
                    Point(
                        start.x + along_ray * direction_x,
                        start.y + along_ray * direction_y,
                    ),
                )
            )
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _add_shape(
    scene: DrawingScene,
    element_id: str,
    semantic_id: str | None,
    role: str,
    classes: set[str],
    style: ElementStyle,
    box: Box,
    shape: str,
    *,
    points: list[Point] | None = None,
) -> SceneShape | SceneContainer:
    target_id = semantic_id or element_id
    cls = SceneContainer if "cluster" in classes else SceneShape
    if cls is SceneContainer:
        item: SceneShape | SceneContainer = SceneContainer(
            id=element_id,
            semantic_id=target_id,
            role="group.default",
            classes=classes,
            style=style,
            z_index=_svg_order(element_id),
            box=box,
            label="",
        )
    else:
        item = SceneShape(
            id=element_id,
            semantic_id=target_id,
            role=role,
            classes=classes,
            style=style,
            z_index=_svg_order(element_id),
            box=box,
            shape=shape,
            text="",
            points=list(points or []),
        )
    scene.add(item)
    return item


def _add_connector(
    scene: DrawingScene,
    element_id: str,
    semantic_id: str | None,
    role: str,
    classes: set[str],
    style: ElementStyle,
    points: list[Point],
    element: ET.Element,
) -> None:
    if len(points) < 2 or _invisible(style):
        return
    target_id = semantic_id or element_id
    source_id = element.get("data-from")
    target_target_id = element.get("data-to")
    if "->" in target_id:
        source_id, target_target_id = target_id.split("->", 1)
    scene.add(
        SceneConnector(
            id=element_id,
            semantic_id=target_id,
            role=role if role != "node.default" else "edge.default",
            classes=classes,
            style=style,
            z_index=_svg_order(element_id),
            points=_deduplicate(points),
            source_id=source_id,
            target_id=target_target_id,
            directed=bool(element.get("marker-end")),
            start_marker=_marker_kind(element.get("marker-start")),
            end_marker=_marker_kind(element.get("marker-end")),
            metadata={
                "svg_id": element.get("id"),
                "marker_start": element.get("marker-start"),
                "marker_end": element.get("marker-end"),
            },
        )
    )


def _marker_kind(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if "extension" in lowered or "triangle" in lowered:
        return "triangle"
    if "aggregation" in lowered or "composition" in lowered or "diamond" in lowered:
        return "diamond"
    if "circle" in lowered or "oval" in lowered:
        return "oval"
    return "arrow"


def _parse_css(root: ET.Element) -> _Stylesheet:
    result = _Stylesheet(root={}, rules=[])
    root_id = root.get("id")
    rule_order = 0
    for element in root.iter():
        if _local(element.tag) != "style":
            continue
        text = "".join(element.itertext())
        for selector_text, declarations in _CSS_RULE_RE.findall(text):
            parsed = _parse_declarations(declarations)
            for selector in selector_text.split(","):
                selector = selector.strip()
                rule_order += 1
                if selector in {"svg", ":root"} or (
                    root_id and selector in {f"#{root_id}", f"#{root_id} svg"}
                ):
                    result.root.update(parsed)
                    continue
                if ":" in selector or "[" in selector:
                    continue
                class_matches = frozenset(re.findall(r"\.([A-Za-z_][\w-]*)", selector))
                last_component = selector.split()[-1]
                tag_match = re.match(r"^([A-Za-z_][\w-]*)", last_component)
                target_tag = tag_match.group(1) if tag_match else None
                if not class_matches and target_tag is None:
                    continue
                result.rules.append(
                    _CssRule(
                        required_classes=class_matches,
                        target_tag=target_tag,
                        declarations=parsed,
                        specificity=(
                            len(re.findall(r"#[A-Za-z_][\w-]*", selector)),
                            len(class_matches),
                            1 if target_tag else 0,
                        ),
                        order=rule_order,
                    )
                )
    return result


def _element_declarations(
    element: ET.Element,
    classes: set[str],
    css: _Stylesheet,
    inherited_style: dict[str, str],
) -> dict[str, str]:
    declarations = dict(css.root)
    declarations.update(inherited_style)
    for name in (
        "fill",
        "fill-opacity",
        "stroke",
        "stroke-opacity",
        "color",
        "stroke-width",
        "stroke-dasharray",
        "opacity",
        "font-family",
        "font-size",
        "font-style",
        "font-weight",
        "text-anchor",
        "dominant-baseline",
        "display",
        "visibility",
        "transform-origin",
    ):
        if element.get(name) is not None:
            declarations[name] = element.get(name, "")
    tag = _local(element.tag)
    matching_rules = [
        rule
        for rule in css.rules
        if rule.required_classes <= classes and (rule.target_tag is None or rule.target_tag == tag)
    ]
    for rule in sorted(
        matching_rules,
        key=lambda item: (item.specificity, item.order),
    ):
        declarations.update(rule.declarations)
    declarations.update(_parse_declarations(element.get("style", "")))
    return declarations


def _element_style(
    element: ET.Element,
    classes: set[str],
    css: _Stylesheet,
    paint_servers: dict[str, str],
    inherited_style: dict[str, str],
) -> ElementStyle:
    declarations = _element_declarations(element, classes, css, inherited_style)
    return _style_from_declarations(declarations, paint_servers)


def _foreign_object_text_style(
    element: ET.Element,
    classes: set[str],
    css: _Stylesheet,
    paint_servers: dict[str, str],
    inherited_style: dict[str, str],
) -> ElementStyle:
    descendant_classes = set(classes)
    candidates: list[ET.Element] = []
    for descendant in element.iter():
        if descendant is element:
            continue
        descendant_classes.update(descendant.get("class", "").split())
        if _local(descendant.tag) in {"span", "p", "div"}:
            candidates.append(descendant)
    target = next(
        (item for item in candidates if _local(item.tag) == "span"),
        candidates[-1] if candidates else element,
    )
    declarations = _element_declarations(
        target,
        descendant_classes,
        css,
        inherited_style,
    )
    return _style_from_declarations(declarations, paint_servers)


def _style_from_declarations(
    declarations: dict[str, str],
    paint_servers: dict[str, str],
) -> ElementStyle:
    line_width = _length(declarations.get("stroke-width"), 1.4)
    opacity = None
    if declarations.get("opacity"):
        try:
            opacity = float(declarations["opacity"])
        except ValueError:
            opacity = None
    dash_value = re.sub(
        r"\s*!important\s*$",
        "",
        declarations.get("stroke-dasharray", ""),
        flags=re.IGNORECASE,
    )
    dash_numbers = _numbers(dash_value)
    has_dash = dash_value.lower() not in {"", "none"} and not (
        dash_numbers and all(abs(item) < 1e-9 for item in dash_numbers)
    )
    current_color = _color_or_none(declarations.get("color"))
    fill = _paint_or_none(declarations.get("fill"), current_color, paint_servers)
    line = _paint_or_none(declarations.get("stroke"), current_color, paint_servers)
    return ElementStyle(
        fill=_color_with_alpha(fill, declarations.get("fill-opacity")),
        line=_color_with_alpha(line, declarations.get("stroke-opacity")),
        text=current_color,
        line_width=line_width,
        dash="dash" if has_dash else None,
        font_family=declarations.get("font-family"),
        font_size=_length(declarations.get("font-size"), 0.0) or None,
        bold=_font_weight_is_bold(declarations.get("font-weight")),
        italic=_font_style_is_italic(declarations.get("font-style")),
        opacity=opacity,
    )


def _font_weight_is_bold(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"bold", "bolder"}:
        return True
    try:
        return int(float(lowered)) >= 600
    except ValueError:
        return False


def _font_style_is_italic(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in {"italic", "oblique"}


def _parse_declarations(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in text.split(";"):
        if ":" in part:
            name, value = part.split(":", 1)
            result[name.strip().lower()] = value.strip()
    return result


def _color_or_none(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    text = value.strip()
    return text.lower() if text.lower() == "none" else normalize_color(text)


def _paint_or_none(
    value: str | None,
    current_color: str | None,
    paint_servers: dict[str, str],
) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.IGNORECASE)
    if text.lower() == "currentcolor":
        return current_color or "#000000"
    paint_match = re.fullmatch(r"url\(\s*#([^)]+)\s*\)", text, flags=re.IGNORECASE)
    if paint_match:
        return paint_servers.get(paint_match.group(1), current_color)
    if "nan" in text.lower():
        return current_color
    return _color_or_none(text)


def _color_with_alpha(color: str | None, alpha_text: str | None) -> str | None:
    if color is None or alpha_text is None:
        return color
    match = re.fullmatch(r"#([0-9A-Fa-f]{6})(?:[0-9A-Fa-f]{2})?", color)
    if not match:
        return color
    try:
        alpha = max(0.0, min(1.0, float(alpha_text)))
    except ValueError:
        return color
    return f"#{match.group(1).upper()}{round(alpha * 255):02X}"


def _parse_paint_servers(root: ET.Element) -> dict[str, str]:
    """Approximate SVG gradients with their first usable stop color."""

    result: dict[str, str] = {}
    for element in root.iter():
        if _local(element.tag) not in {"linearGradient", "radialGradient"}:
            continue
        identifier = element.get("id")
        if not identifier:
            continue
        colors: list[str] = []
        for stop in element:
            if _local(stop.tag) != "stop":
                continue
            declarations = _parse_declarations(stop.get("style", ""))
            value = stop.get("stop-color") or declarations.get("stop-color")
            color = _color_or_none(value)
            if color and color not in {"none", "#00000000"}:
                colors.append(color)
        if colors:
            result[identifier] = colors[0]
    return result


def _semantic_id(value: str | None, classes: set[str]) -> str | None:
    if not value:
        return None
    text = re.sub(r"^(?:my-svg-|mermaid-)", "", value)
    patterns = [
        r"^i(\d+)$",
        r"(?:flowchart|state)-(.+?)-\d+$",
        r"classId-(.+?)-\d+$",
        r"entity-(.+?)-\d+$",
        r"(?:cluster|subGraph)-(.+?)-\d*$",
        r"L_(.+?)_(.+?)_\d+$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if pattern == r"^i(\d+)$":
                return f"event-{match.group(1)}"
            if len(match.groups()) == 1:
                return match.group(1)
            return f"{match.group(1)}->{match.group(2)}"
    return text


def _role(classes: set[str], tag: str) -> str:
    joined = " ".join(classes).lower()
    if "cluster" in joined:
        return "group.default"
    if "messageline" in joined or "message" in joined:
        return "sequence.message"
    if "edge" in joined or "transition" in joined or tag in {"line", "polyline"}:
        return "edge.default"
    if "actor" in joined:
        return "sequence.participant"
    if "note" in joined:
        return "sequence.note"
    if "entity" in joined:
        return "er.entity"
    if "class" in joined:
        return "class.entity"
    return "node.default"


def _parse_transform(value: str) -> _Affine:
    transform = _Affine()
    for name, arguments in _TRANSFORM_RE.findall(value):
        values = _numbers(arguments)
        current = _Affine()
        if name == "matrix" and len(values) >= 6:
            current = _Affine(*values[:6])
        elif name == "translate" and values:
            current = _Affine(e=values[0], f=values[1] if len(values) > 1 else 0.0)
        elif name == "scale" and values:
            current = _Affine(a=values[0], d=values[1] if len(values) > 1 else values[0])
        elif name == "rotate" and values:
            angle = radians(values[0])
            rotation = _Affine(a=cos(angle), b=sin(angle), c=-sin(angle), d=cos(angle))
            if len(values) >= 3:
                cx, cy = values[1:3]
                current = _Affine(e=-cx, f=-cy).then(rotation).then(_Affine(e=cx, f=cy))
            else:
                current = rotation
        transform = current.then(transform)
    return transform


def _transform_with_origin(value: str, origin: str | None) -> _Affine:
    transform = _parse_transform(value)
    origin_values = _numbers(origin or "")
    if len(origin_values) < 2:
        return transform
    origin_x, origin_y = origin_values[:2]
    return _Affine(e=-origin_x, f=-origin_y).then(transform).then(_Affine(e=origin_x, f=origin_y))


def _svg_viewport_transform(element: ET.Element) -> _Affine:
    view_box = _numbers(element.get("viewBox", ""))
    if len(view_box) < 4:
        return _Affine(
            e=_length(element.get("x"), 0.0),
            f=_length(element.get("y"), 0.0),
        )
    min_x, min_y, view_width, view_height = view_box[:4]
    width = _length(element.get("width"), view_width)
    height = _length(element.get("height"), view_height)
    if view_width <= 0 or view_height <= 0 or width <= 0 or height <= 0:
        return _Affine()
    scale = min(width / view_width, height / view_height)
    offset_x = _length(element.get("x"), 0.0) + (width - view_width * scale) / 2
    offset_y = _length(element.get("y"), 0.0) + (height - view_height * scale) / 2
    return (
        _Affine(e=-min_x, f=-min_y)
        .then(_Affine(a=scale, d=scale))
        .then(_Affine(e=offset_x, f=offset_y))
    )


def _transformed_box(box: Box, transform: _Affine) -> Box:
    points = [
        transform.apply(Point(box.x, box.y)),
        transform.apply(Point(box.x + box.width, box.y)),
        transform.apply(Point(box.x, box.y + box.height)),
        transform.apply(Point(box.x + box.width, box.y + box.height)),
    ]
    return _box_for_points(points)


def _transformed_primitive_box(box: Box, transform: _Affine) -> tuple[Box, float]:
    center = transform.apply(box.center)
    width = box.width * hypot(transform.a, transform.b)
    height = box.height * hypot(transform.c, transform.d)
    return (
        Box(
            center.x - width / 2,
            center.y - height / 2,
            width,
            height,
        ),
        degrees(atan2(transform.b, transform.a)),
    )


def _box_for_points(points: Iterable[Point]) -> Box:
    items = list(points)
    min_x = min(item.x for item in items)
    min_y = min(item.y for item in items)
    max_x = max(item.x for item in items)
    max_y = max(item.y for item in items)
    return Box(min_x, min_y, max(max_x - min_x, 0.01), max(max_y - min_y, 0.01))


def _point_pairs(value: str, transform: _Affine) -> list[Point]:
    values = _numbers(value)
    return [
        transform.apply(Point(values[index], values[index + 1]))
        for index in range(0, len(values) - 1, 2)
    ]


def _path_points(value: str, transform: _Affine) -> list[Point]:
    """Approximate an SVG path with points while honoring relative commands."""

    tokens = _PATH_TOKEN_RE.findall(value)
    arity = {
        "M": 2,
        "L": 2,
        "H": 1,
        "V": 1,
        "C": 6,
        "S": 4,
        "Q": 4,
        "T": 2,
        "A": 7,
    }
    points: list[Point] = []
    current = Point(0.0, 0.0)
    subpath_start = current
    last_control: Point | None = None
    command: str | None = None
    last_was_move = False
    index = 0

    def point(x: float, y: float, *, relative: bool) -> Point:
        if relative:
            return Point(current.x + x, current.y + y)
        return Point(x, y)

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command.upper() == "Z":
                current = subpath_start
                points.append(current)
                last_control = None
                last_was_move = False
                command = None
            continue
        if command is None:
            index += 1
            continue
        upper = command.upper()
        required = arity.get(upper)
        if required is None or index + required > len(tokens):
            break
        values = [float(item) for item in tokens[index : index + required]]
        index += required
        relative = command.islower()

        if upper == "M":
            current = point(values[0], values[1], relative=relative)
            subpath_start = current
            if last_was_move and points:
                points[-1] = current
            else:
                points.append(current)
            command = "l" if relative else "L"
            last_control = None
            last_was_move = True
        elif upper == "L":
            current = point(values[0], values[1], relative=relative)
            points.append(current)
            last_control = None
            last_was_move = False
        elif upper == "H":
            current = Point(
                current.x + values[0] if relative else values[0],
                current.y,
            )
            points.append(current)
            last_control = None
            last_was_move = False
        elif upper == "V":
            current = Point(
                current.x,
                current.y + values[0] if relative else values[0],
            )
            points.append(current)
            last_control = None
            last_was_move = False
        elif upper == "C":
            control1 = point(values[0], values[1], relative=relative)
            control2 = point(values[2], values[3], relative=relative)
            destination = point(values[4], values[5], relative=relative)
            points.extend(_sample_cubic(current, control1, control2, destination))
            current = destination
            last_control = control2
            last_was_move = False
        elif upper == "S":
            control1 = (
                Point(
                    2 * current.x - last_control.x,
                    2 * current.y - last_control.y,
                )
                if last_control is not None
                else current
            )
            control2 = point(values[0], values[1], relative=relative)
            destination = point(values[2], values[3], relative=relative)
            points.extend(_sample_cubic(current, control1, control2, destination))
            current = destination
            last_control = control2
            last_was_move = False
        elif upper == "Q":
            control = point(values[0], values[1], relative=relative)
            destination = point(values[2], values[3], relative=relative)
            points.extend(_sample_quadratic(current, control, destination))
            current = destination
            last_control = control
            last_was_move = False
        elif upper == "T":
            control = (
                Point(
                    2 * current.x - last_control.x,
                    2 * current.y - last_control.y,
                )
                if last_control is not None
                else current
            )
            destination = point(values[0], values[1], relative=relative)
            points.extend(_sample_quadratic(current, control, destination))
            current = destination
            last_control = control
            last_was_move = False
        elif upper == "A":
            destination = point(values[5], values[6], relative=relative)
            points.extend(
                _sample_arc(
                    current,
                    rx=values[0],
                    ry=values[1],
                    axis_rotation=values[2],
                    large_arc=bool(values[3]),
                    sweep=bool(values[4]),
                    end=destination,
                )
            )
            current = destination
            last_control = None
            last_was_move = False
    return [transform.apply(item) for item in points]


def _sample_arc(
    start: Point,
    *,
    rx: float,
    ry: float,
    axis_rotation: float,
    large_arc: bool,
    sweep: bool,
    end: Point,
) -> list[Point]:
    """Approximate one SVG elliptical arc using endpoint parameterization."""

    rx = abs(rx)
    ry = abs(ry)
    if rx < 1e-9 or ry < 1e-9 or (abs(start.x - end.x) < 1e-9 and abs(start.y - end.y) < 1e-9):
        return [end]

    phi = radians(axis_rotation % 360)
    cos_phi = cos(phi)
    sin_phi = sin(phi)
    half_dx = (start.x - end.x) / 2
    half_dy = (start.y - end.y) / 2
    x1_prime = cos_phi * half_dx + sin_phi * half_dy
    y1_prime = -sin_phi * half_dx + cos_phi * half_dy

    scale = (x1_prime**2) / (rx**2) + (y1_prime**2) / (ry**2)
    if scale > 1:
        correction = sqrt(scale)
        rx *= correction
        ry *= correction

    numerator = max(
        0.0,
        rx**2 * ry**2 - rx**2 * y1_prime**2 - ry**2 * x1_prime**2,
    )
    denominator = rx**2 * y1_prime**2 + ry**2 * x1_prime**2
    coefficient = 0.0 if denominator < 1e-12 else sqrt(numerator / denominator)
    if large_arc == sweep:
        coefficient = -coefficient

    center_x_prime = coefficient * (rx * y1_prime / ry)
    center_y_prime = coefficient * (-ry * x1_prime / rx)
    center_x = cos_phi * center_x_prime - sin_phi * center_y_prime + (start.x + end.x) / 2
    center_y = sin_phi * center_x_prime + cos_phi * center_y_prime + (start.y + end.y) / 2

    start_angle = atan2(
        (y1_prime - center_y_prime) / ry,
        (x1_prime - center_x_prime) / rx,
    )
    end_angle = atan2(
        (-y1_prime - center_y_prime) / ry,
        (-x1_prime - center_x_prime) / rx,
    )
    delta = end_angle - start_angle
    if not sweep and delta > 0:
        delta -= 2 * pi
    elif sweep and delta < 0:
        delta += 2 * pi

    # Five-degree segments keep editable PowerPoint freeforms visually smooth
    # at presentation scale without introducing Bézier-only geometry.
    segment_count = max(2, ceil(abs(delta) / (pi / 36)))
    result: list[Point] = []
    for index in range(1, segment_count + 1):
        angle = start_angle + delta * index / segment_count
        result.append(
            Point(
                center_x + cos_phi * rx * cos(angle) - sin_phi * ry * sin(angle),
                center_y + sin_phi * rx * cos(angle) + cos_phi * ry * sin(angle),
            )
        )
    result[-1] = end
    return result


def _sample_cubic(
    start: Point,
    control1: Point,
    control2: Point,
    end: Point,
) -> list[Point]:
    result: list[Point] = []
    for step in range(1, 5):
        t = step / 4
        inverse = 1 - t
        result.append(
            Point(
                inverse**3 * start.x
                + 3 * inverse**2 * t * control1.x
                + 3 * inverse * t**2 * control2.x
                + t**3 * end.x,
                inverse**3 * start.y
                + 3 * inverse**2 * t * control1.y
                + 3 * inverse * t**2 * control2.y
                + t**3 * end.y,
            )
        )
    return result


def _sample_quadratic(
    start: Point,
    control: Point,
    end: Point,
) -> list[Point]:
    result: list[Point] = []
    for step in range(1, 5):
        t = step / 4
        inverse = 1 - t
        result.append(
            Point(
                inverse**2 * start.x + 2 * inverse * t * control.x + t**2 * end.x,
                inverse**2 * start.y + 2 * inverse * t * control.y + t**2 * end.y,
            )
        )
    return result


def _numbers(value: str) -> list[float]:
    return [float(item) for item in _NUMBER_RE.findall(value)]


def _first_number(value: str | None, default: float) -> float:
    values = _numbers(value or "")
    return values[0] if values else default


def _length(value: str | None, default: float) -> float:
    if value is None:
        return default
    match = _NUMBER_RE.search(value)
    return float(match.group(0)) if match else default


def _text_position(element: ET.Element, font_size: float) -> tuple[float, float]:
    first_tspan = next(
        (child for child in element.iter() if _local(child.tag) == "tspan"),
        None,
    )
    x_value = element.get("x")
    y_value = element.get("y")
    if first_tspan is not None:
        x_value = first_tspan.get("x") or x_value
        y_value = first_tspan.get("y") or y_value
    x = _css_length(x_value, 0.0, font_size)
    y = _css_length(y_value, 0.0, font_size)
    dy_values = [element.get("dy")]
    if first_tspan is not None:
        dy_values.append(first_tspan.get("dy"))
    for dy_value in dy_values:
        y += _css_length(dy_value, 0.0, font_size)
    return x, y


def _css_length(value: str | None, default: float, font_size: float) -> float:
    if value is None:
        return default
    number = _first_number(value, default)
    lowered = value.strip().lower()
    if lowered.endswith("em"):
        return number * font_size
    if lowered.endswith("ex"):
        return number * font_size * 0.5
    return number


def _estimated_text_width(text: str, font_size: float) -> float:
    widest = 0.0
    for line in text.splitlines() or [""]:
        units = 0.0
        for character in line:
            if east_asian_width(character) in {"W", "F"}:
                units += 1.0
            elif character.isspace():
                units += 0.33
            elif character in ".,:;!|'`ijlItf()[]{}":
                units += 0.34
            elif character.isupper():
                units += 0.62
            else:
                units += 0.55
        widest = max(widest, units)
    return max(widest * font_size, font_size * 0.5)


def _svg_text_content(element: ET.Element) -> str:
    direct_tspans = [child for child in element if _local(child.tag) == "tspan"]
    if len(direct_tspans) > 1:
        lines = [_clean_text(" ".join(child.itertext())) for child in direct_tspans]
        return "\n".join(line for line in lines if line)
    return _clean_text(" ".join(element.itertext()))


def _svg_order(element_id: str) -> int:
    try:
        return int(element_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def _looks_like_diamond(points: list[Point]) -> bool:
    box = _box_for_points(points)
    center = box.center
    tolerance = max(box.width, box.height) * 0.15
    return all(
        min(
            abs(point.x - center.x),
            abs(point.y - center.y),
        )
        <= tolerance
        for point in points
    )


def _invisible(style: ElementStyle) -> bool:
    return style.opacity == 0 or (
        style.fill in {"none", "#00000000", "transparent"}
        and style.line in {"none", "#00000000", "transparent"}
    )


def _deduplicate(points: list[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    return result


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
