"""Renderer-neutral diagram and positioned-layout models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiagramError(ValueError):
    """Base exception for invalid diagram input."""


class NodeShape(str, Enum):
    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    DIAMOND = "diamond"
    ELLIPSE = "ellipse"
    HEXAGON = "hexagon"
    STADIUM = "stadium"
    SUBPROCESS = "subprocess"
    CUSTOM = "custom"


@dataclass(slots=True)
class DiagramNode:
    id: str
    label: str
    shape: NodeShape = NodeShape.RECTANGLE
    style: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    group_id: str | None = None


@dataclass(slots=True)
class DiagramEdge:
    source: str
    target: str
    label: str | None = None
    directed: bool = True
    style: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiagramGroup:
    id: str
    label: str
    node_ids: list[str] = field(default_factory=list)
    parent_id: str | None = None
    style: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Diagram:
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    groups: list[DiagramGroup] = field(default_factory=list)
    direction: str = "LR"
    metadata: dict[str, Any] = field(default_factory=dict)

    def node_map(self) -> dict[str, DiagramNode]:
        return {node.id: node for node in self.nodes}

    def validate(self) -> None:
        direction = self.direction.upper()
        if direction == "TD":
            direction = "TB"
        if direction not in {"LR", "RL", "TB", "BT"}:
            raise DiagramError(f"Unsupported direction: {self.direction!r}")
        self.direction = direction

        node_ids = [node.id for node in self.nodes]
        if any(not node_id for node_id in node_ids):
            raise DiagramError("Node ids must not be empty")
        duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
        if duplicates:
            raise DiagramError(f"Duplicate node ids: {', '.join(duplicates)}")

        known_nodes = set(node_ids)
        for edge in self.edges:
            missing = {edge.source, edge.target} - known_nodes
            if missing:
                raise DiagramError(
                    f"Edge {edge.source!r} -> {edge.target!r} references unknown nodes: "
                    f"{', '.join(sorted(missing))}"
                )

        group_ids = {group.id for group in self.groups}
        if len(group_ids) != len(self.groups):
            raise DiagramError("Group ids must be unique")
        for group in self.groups:
            unknown = set(group.node_ids) - known_nodes
            if unknown:
                raise DiagramError(
                    f"Group {group.id!r} references unknown nodes: {', '.join(sorted(unknown))}"
                )
            if group.parent_id is not None and group.parent_id not in group_ids:
                raise DiagramError(
                    f"Group {group.id!r} references unknown parent {group.parent_id!r}"
                )


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class PositionedNode:
    node: DiagramNode
    x: float
    y: float
    width: float
    height: float
    rank: int = 0
    order: int = 0

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)


@dataclass(slots=True)
class RoutedEdge:
    edge: DiagramEdge
    points: list[Point]


@dataclass(slots=True)
class PositionedGroup:
    group: DiagramGroup
    x: float
    y: float
    width: float
    height: float


@dataclass(slots=True)
class DiagramLayout:
    nodes: list[PositionedNode]
    edges: list[RoutedEdge]
    groups: list[PositionedGroup] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    direction: str = "LR"
    metadata: dict[str, Any] = field(default_factory=dict)

    def node_map(self) -> dict[str, PositionedNode]:
        return {positioned.node.id: positioned for positioned in self.nodes}
