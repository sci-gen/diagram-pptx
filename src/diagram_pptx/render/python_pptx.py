"""Render positioned diagrams as editable, native python-pptx shapes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import pairwise
from math import hypot
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from ..model import DiagramLayout, NodeShape, Point, PositionedNode, RoutedEdge


@dataclass(frozen=True, slots=True)
class RenderTheme:
    node_fill: str = "#EAF2FF"
    node_line: str = "#3167A5"
    node_text: str = "#16324F"
    edge_line: str = "#536273"
    edge_label_fill: str = "#FFFFFF"
    group_line: str = "#8FA4B8"
    group_text: str = "#52687A"
    font_family: str = "Aptos"
    node_font_size: float = 15.0
    edge_font_size: float = 11.0
    group_font_size: float = 11.0
    line_width: float = 1.4


@dataclass(slots=True)
class RenderResult:
    node_shapes: dict[str, Any] = field(default_factory=dict)
    connectors: list[Any] = field(default_factory=list)
    edge_label_shapes: list[Any] = field(default_factory=list)
    group_shapes: list[Any] = field(default_factory=list)

    @property
    def shapes(self) -> list[Any]:
        return [
            *self.group_shapes,
            *self.connectors,
            *self.node_shapes.values(),
            *self.edge_label_shapes,
        ]


@dataclass(frozen=True, slots=True)
class _Transform:
    logical_left: float
    logical_top: float
    scale: float
    offset_x: float
    offset_y: float

    def point(self, point: Point) -> tuple[Any, Any]:
        return (
            Inches(self.offset_x + (point.x - self.logical_left) * self.scale),
            Inches(self.offset_y + (point.y - self.logical_top) * self.scale),
        )

    def box(self, x: float, y: float, width: float, height: float) -> tuple[Any, Any, Any, Any]:
        left, top = self.point(Point(x, y))
        return left, top, Inches(width * self.scale), Inches(height * self.scale)


class PythonPptxRenderer:
    """Render a :class:`DiagramLayout` to a ``python-pptx`` slide.

    Coordinates in ``bounds`` are inches. Connectors are emitted before nodes
    so they remain behind node shapes. Orthogonal paths use multiple native
    straight connectors because python-pptx does not yet expose stable elbow
    waypoint control.
    """

    DEFAULT_SHAPE_REGISTRY = {
        NodeShape.RECTANGLE: MSO_SHAPE.RECTANGLE,
        NodeShape.ROUNDED_RECTANGLE: MSO_SHAPE.ROUNDED_RECTANGLE,
        NodeShape.DIAMOND: MSO_SHAPE.DIAMOND,
        NodeShape.ELLIPSE: MSO_SHAPE.OVAL,
        NodeShape.HEXAGON: MSO_SHAPE.HEXAGON,
        NodeShape.STADIUM: MSO_SHAPE.ROUNDED_RECTANGLE,
        NodeShape.SUBPROCESS: MSO_SHAPE.FLOWCHART_PREDEFINED_PROCESS,
    }

    def __init__(
        self,
        *,
        theme: RenderTheme | None = None,
        shape_registry: dict[NodeShape, Any] | None = None,
        inner_padding: float = 0.12,
    ) -> None:
        self.theme = theme or RenderTheme()
        self.shape_registry = dict(self.DEFAULT_SHAPE_REGISTRY)
        if shape_registry:
            self.shape_registry.update(shape_registry)
        self.inner_padding = inner_padding

    def render(
        self,
        layout: DiagramLayout,
        *,
        target: Any | None = None,
        slide: Any | None = None,
        bounds: tuple[float, float, float, float],
        **_: Any,
    ) -> RenderResult:
        """Render into ``target`` (or legacy-friendly ``slide`` alias)."""

        target_slide = target if target is not None else slide
        if target_slide is None:
            raise TypeError("render() requires target=<slide> or slide=<slide>")
        if bounds[2] <= 0 or bounds[3] <= 0:
            raise ValueError("bounds width and height must be positive")
        if not layout.nodes:
            return RenderResult()

        transform = self._build_transform(layout, bounds)
        result = RenderResult()

        # Group outlines are backgrounds, followed by edges, nodes, and labels.
        for positioned_group in layout.groups:
            result.group_shapes.extend(
                self._render_group(target_slide, positioned_group, transform)
            )

        for routed_edge in layout.edges:
            result.connectors.extend(self._render_edge(target_slide, routed_edge, transform))

        for positioned_node in layout.nodes:
            result.node_shapes[positioned_node.node.id] = self._render_node(
                target_slide, positioned_node, transform
            )

        for routed_edge in layout.edges:
            if routed_edge.edge.label:
                result.edge_label_shapes.append(
                    self._render_edge_label(target_slide, routed_edge, transform)
                )
        return result

    def _build_transform(
        self, layout: DiagramLayout, bounds: tuple[float, float, float, float]
    ) -> _Transform:
        points: list[Point] = []
        for node in layout.nodes:
            points.extend([Point(node.x, node.y), Point(node.x + node.width, node.y + node.height)])
        for group in layout.groups:
            points.extend(
                [Point(group.x, group.y), Point(group.x + group.width, group.y + group.height)]
            )
        for edge in layout.edges:
            points.extend(edge.points)

        min_x = min(point.x for point in points)
        min_y = min(point.y for point in points)
        max_x = max(point.x for point in points)
        max_y = max(point.y for point in points)
        logical_width = max(max_x - min_x, 0.001)
        logical_height = max(max_y - min_y, 0.001)

        left, top, width, height = bounds
        usable_width = max(width - self.inner_padding * 2, 0.001)
        usable_height = max(height - self.inner_padding * 2, 0.001)
        scale = min(usable_width / logical_width, usable_height / logical_height)
        drawn_width = logical_width * scale
        drawn_height = logical_height * scale
        offset_x = left + (width - drawn_width) / 2
        offset_y = top + (height - drawn_height) / 2
        return _Transform(min_x, min_y, scale, offset_x, offset_y)

    def _render_group(self, slide: Any, group: Any, transform: _Transform) -> list[Any]:
        left, top, width, height = transform.box(group.x, group.y, group.width, group.height)
        outline = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
        outline.fill.background()
        outline.line.color.rgb = self._rgb(group.group.style.get("line"), self.theme.group_line)
        outline.line.width = Pt(float(group.group.style.get("line_width", 1.0)))
        self._set_dash(outline.line, group.group.style.get("dash", "dash"))

        label_height = Inches(0.28)
        label = slide.shapes.add_textbox(
            left + Inches(0.1),
            top - Inches(0.01),
            max(width - Inches(0.2), Inches(0.2)),
            label_height,
        )
        self._format_text_frame(
            label.text_frame,
            group.group.label,
            font_size=self.theme.group_font_size,
            color=group.group.style.get("text", self.theme.group_text),
            bold=True,
            alignment=PP_ALIGN.LEFT,
        )
        return [outline, label]

    def _render_edge(self, slide: Any, routed: RoutedEdge, transform: _Transform) -> list[Any]:
        connectors: list[Any] = []
        for index, (begin, end) in enumerate(pairwise(routed.points)):
            begin_x, begin_y = transform.point(begin)
            end_x, end_y = transform.point(end)
            connector = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT, begin_x, begin_y, end_x, end_y
            )
            connector.line.color.rgb = self._rgb(
                routed.edge.style.get("line"), self.theme.edge_line
            )
            connector.line.width = Pt(float(routed.edge.style.get("width", self.theme.line_width)))
            if routed.edge.style.get("dash"):
                self._set_dash(connector.line, routed.edge.style["dash"])
            if routed.edge.directed and index == len(routed.points) - 2:
                self._set_end_arrow(connector.line)
            connectors.append(connector)
        return connectors

    def _render_node(self, slide: Any, positioned: PositionedNode, transform: _Transform) -> Any:
        node = positioned.node
        left, top, width, height = transform.box(
            positioned.x, positioned.y, positioned.width, positioned.height
        )
        shape_type = self.shape_registry.get(node.shape, MSO_SHAPE.RECTANGLE)
        shape = slide.shapes.add_shape(shape_type, left, top, width, height)
        shape.name = f"diagram-node:{node.id}"
        shape.fill.solid()
        shape.fill.fore_color.rgb = self._rgb(node.style.get("fill"), self.theme.node_fill)
        shape.line.color.rgb = self._rgb(node.style.get("line"), self.theme.node_line)
        shape.line.width = Pt(float(node.style.get("line_width", self.theme.line_width)))
        if node.style.get("dash"):
            self._set_dash(shape.line, node.style["dash"])

        self._format_text_frame(
            shape.text_frame,
            node.label,
            font_size=float(node.style.get("font_size", self.theme.node_font_size)),
            color=node.style.get("text", self.theme.node_text),
            bold=bool(node.style.get("bold", False)),
            alignment=PP_ALIGN.CENTER,
        )
        shape.text_frame.margin_left = Inches(0.08)
        shape.text_frame.margin_right = Inches(0.08)
        shape.text_frame.margin_top = Inches(0.04)
        shape.text_frame.margin_bottom = Inches(0.04)
        return shape

    def _render_edge_label(self, slide: Any, routed: RoutedEdge, transform: _Transform) -> Any:
        midpoint = self._path_midpoint(routed.points)
        center_x, center_y = transform.point(midpoint)
        label_width = Inches(max(0.58, min(2.2, 0.24 + len(routed.edge.label or "") * 0.09)))
        label_height = Inches(0.3)
        label = slide.shapes.add_textbox(
            center_x - label_width / 2,
            center_y - label_height / 2,
            label_width,
            label_height,
        )
        label.fill.solid()
        label.fill.fore_color.rgb = self._rgb(
            routed.edge.style.get("label_fill"), self.theme.edge_label_fill
        )
        label.line.fill.background()
        self._format_text_frame(
            label.text_frame,
            routed.edge.label or "",
            font_size=self.theme.edge_font_size,
            color=routed.edge.style.get("text", self.theme.edge_line),
            bold=False,
            alignment=PP_ALIGN.CENTER,
        )
        return label

    def _format_text_frame(
        self,
        text_frame: Any,
        text: str,
        *,
        font_size: float,
        color: str,
        bold: bool,
        alignment: Any,
    ) -> None:
        text_frame.clear()
        text_frame.word_wrap = True
        text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        paragraph = text_frame.paragraphs[0]
        paragraph.alignment = alignment
        run = paragraph.add_run()
        run.text = text
        run.font.name = self.theme.font_family
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = self._rgb(color, self.theme.node_text)

    @staticmethod
    def _path_midpoint(points: list[Point]) -> Point:
        if len(points) == 1:
            return points[0]
        lengths = [hypot(end.x - begin.x, end.y - begin.y) for begin, end in pairwise(points)]
        target = sum(lengths) / 2
        traversed = 0.0
        for (begin, end), length in zip(pairwise(points), lengths, strict=True):
            if traversed + length >= target and length:
                ratio = (target - traversed) / length
                return Point(
                    begin.x + (end.x - begin.x) * ratio,
                    begin.y + (end.y - begin.y) * ratio,
                )
            traversed += length
        return points[-1]

    @staticmethod
    def _rgb(value: Any, default: str) -> RGBColor:
        text = str(value or default).strip()
        if text.startswith("#"):
            text = text[1:]
        if re.fullmatch(r"[0-9A-Fa-f]{6}", text):
            return RGBColor.from_string(text.upper())
        return RGBColor.from_string(default.removeprefix("#").upper())

    @staticmethod
    def _set_end_arrow(line: Any) -> None:
        line_xml = line._get_or_add_ln()
        for existing in list(line_xml):
            if existing.tag.endswith("tailEnd"):
                line_xml.remove(existing)
        tail_end = OxmlElement("a:tailEnd")
        tail_end.set("type", "triangle")
        tail_end.set("w", "sm")
        tail_end.set("len", "sm")
        line_xml.append(tail_end)

    @staticmethod
    def _set_dash(line: Any, value: Any) -> None:
        normalized = str(value).lower()
        dash_value = (
            "dash"
            if normalized not in {"dot", "sysdot", "dashdot"}
            else {
                "dot": "sysDot",
                "sysdot": "sysDot",
                "dashdot": "dashDot",
            }[normalized]
        )
        line_xml = line._get_or_add_ln()
        for existing in list(line_xml):
            if existing.tag.endswith("prstDash"):
                line_xml.remove(existing)
        preset = OxmlElement("a:prstDash")
        preset.set("val", dash_value)
        line_xml.append(preset)
