"""Renderer-neutral positioned drawing scene."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, radians, sin
from typing import Any, Literal

from .styles import ElementStyle


@dataclass(frozen=True, slots=True)
class Point:
    """Two-dimensional point in backend-defined logical units."""

    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True, slots=True)
class Box:
    """Axis-aligned rectangle in backend-defined logical units."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    def to_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(slots=True)
class SceneElement:
    """Shared renderer-neutral identity, style, and z-order fields."""

    id: str
    semantic_id: str
    role: str
    style: ElementStyle = field(default_factory=ElementStyle)
    classes: set[str] = field(default_factory=set)
    z_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SceneShape(SceneElement):
    """Positioned editable node or marker shape."""

    box: Box = field(default_factory=lambda: Box(0, 0, 1, 1))
    shape: str = "rectangle"
    text: str = ""
    points: list[Point] = field(default_factory=list)
    rotation: float = 0.0


@dataclass(slots=True)
class SceneConnector(SceneElement):
    """Editable routed connector with optional markers and label."""

    points: list[Point] = field(default_factory=list)
    source_id: str | None = None
    target_id: str | None = None
    directed: bool = True
    start_marker: str | None = None
    end_marker: str | None = "arrow"
    label: str | None = None


@dataclass(slots=True)
class SceneText(SceneElement):
    """Positioned standalone text, such as a note or compartment."""

    box: Box = field(default_factory=lambda: Box(0, 0, 1, 0.3))
    text: str = ""
    align: Literal["left", "center", "right"] = "center"
    rotation: float = 0.0


@dataclass(slots=True)
class SceneContainer(SceneElement):
    """Visual boundary for a subgraph, namespace, or composite state."""

    box: Box = field(default_factory=lambda: Box(0, 0, 1, 1))
    label: str = ""


DrawingElement = SceneShape | SceneConnector | SceneText | SceneContainer


@dataclass(slots=True)
class DrawingScene:
    """Complete positioned, renderer-neutral diagram drawing."""

    kind: str
    elements: list[DrawingElement] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, element: DrawingElement) -> DrawingElement:
        self.elements.append(element)
        return element

    def ordered_elements(self) -> list[DrawingElement]:
        ordered = sorted(
            enumerate(self.elements),
            key=lambda item: (item[1].z_index, item[0]),
        )
        return [item for _, item in ordered]

    def by_semantic_id(self, semantic_id: str) -> list[DrawingElement]:
        return [item for item in self.elements if item.semantic_id == semantic_id]

    def recompute_extents(self, *, padding: float = 0.0) -> None:
        points: list[Point] = []
        for element in self.elements:
            if isinstance(element, (SceneShape, SceneText, SceneContainer)):
                rotation = element.rotation if isinstance(element, (SceneShape, SceneText)) else 0.0
                if abs(rotation) > 1e-9:
                    angle = radians(rotation)
                    cosine = cos(angle)
                    sine = sin(angle)
                    center = element.box.center
                    for x, y in (
                        (element.box.x, element.box.y),
                        (element.box.x + element.box.width, element.box.y),
                        (
                            element.box.x + element.box.width,
                            element.box.y + element.box.height,
                        ),
                        (element.box.x, element.box.y + element.box.height),
                    ):
                        dx = x - center.x
                        dy = y - center.y
                        points.append(
                            Point(
                                center.x + cosine * dx - sine * dy,
                                center.y + sine * dx + cosine * dy,
                            )
                        )
                else:
                    points.extend(
                        [
                            Point(element.box.x, element.box.y),
                            Point(
                                element.box.x + element.box.width,
                                element.box.y + element.box.height,
                            ),
                        ]
                    )
            elif isinstance(element, SceneConnector):
                points.extend(element.points)
        if not points:
            self.width = self.height = 0.0
            return
        min_x = min(point.x for point in points) - padding
        min_y = min(point.y for point in points) - padding
        max_x = max(point.x for point in points) + padding
        max_y = max(point.y for point in points) + padding
        if min_x != 0 or min_y != 0:
            self.translate(-min_x, -min_y)
        self.width = max_x - min_x
        self.height = max_y - min_y

    def translate(self, dx: float, dy: float) -> None:
        for element in self.elements:
            if isinstance(element, (SceneShape, SceneText, SceneContainer)):
                element.box = Box(
                    element.box.x + dx,
                    element.box.y + dy,
                    element.box.width,
                    element.box.height,
                )
                if isinstance(element, SceneShape) and element.points:
                    element.points = [Point(point.x + dx, point.y + dy) for point in element.points]
            elif isinstance(element, SceneConnector):
                element.points = [Point(point.x + dx, point.y + dy) for point in element.points]
            label_point = element.metadata.get("label_point")
            if isinstance(label_point, (list, tuple)) and len(label_point) == 2:
                element.metadata["label_point"] = (
                    float(label_point[0]) + dx,
                    float(label_point[1]) + dy,
                )
