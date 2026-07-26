"""Typed semantic diagram models and temporary flow-layout compatibility types."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypeVar

from .diagnostics import Diagnostic
from .scene import Point
from .styles import ElementStyle


class DiagramError(ValueError):
    """Raised when a semantic model is internally inconsistent."""


class NodeShape(str, Enum):
    """Semantic node shapes supported by the Native PowerPoint renderer."""

    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    DIAMOND = "diamond"
    ELLIPSE = "ellipse"
    HEXAGON = "hexagon"
    STADIUM = "stadium"
    SUBPROCESS = "subprocess"
    CYLINDER = "cylinder"
    PARALLELOGRAM = "parallelogram"
    CUSTOM = "custom"


@dataclass(slots=True)
class SemanticElement:
    """Shared identity, label, role, classes, style, and metadata fields."""

    id: str
    label: str = ""
    role: str = ""
    classes: set[str] = field(default_factory=set)
    style: ElementStyle = field(default_factory=ElementStyle)
    metadata: dict[str, Any] = field(default_factory=dict)

    def _base_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "role": self.role,
            "classes": sorted(self.classes),
            "style": self.style.to_dict(),
            "metadata": dict(self.metadata),
        }


TElement = TypeVar("TElement", bound=SemanticElement)


class SelectableDiagram:
    """Common query helpers for the ORM-like public object model."""

    def elements(self) -> Iterable[SemanticElement]:
        raise NotImplementedError

    def select(
        self,
        *,
        role: str | None = None,
        class_: str | None = None,
    ) -> list[SemanticElement]:
        """Return elements matching an optional semantic role and class name."""

        return [
            element
            for element in self.elements()
            if (role is None or element.role == role)
            and (class_ is None or class_ in element.classes)
        ]

    def save(self, path: str | Path, **options: Any) -> Any:
        """Save this typed diagram as SVG, PNG, or JPEG.

        The format is inferred from the path suffix. PNG and JPEG require the
        optional ``diagram-pptx[image]`` dependencies.
        """

        from .export import save_diagram

        return save_diagram(self, path, **options)

    def to_svg(self, **options: Any) -> str:
        """Return this diagram as self-contained SVG text."""

        from .export import to_svg

        return to_svg(self, **options)

    def to_png(self, **options: Any) -> bytes:
        """Return PNG bytes; accepts ``dpi``, dimensions, and compile options."""

        from .export import to_png

        return to_png(self, **options)

    def to_jpeg(self, **options: Any) -> bytes:
        """Return JPEG bytes with transparency flattened onto a background."""

        from .export import to_jpeg

        return to_jpeg(self, **options)


class DiagramModel(Protocol):
    kind: str
    metadata: dict[str, Any]

    def validate(self) -> None: ...

    def to_dict(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class MermaidSourceDiagram(SelectableDiagram):
    """Lossless Mermaid source model for Official-only syntax families.

    This model makes every Mermaid family usable without pretending that a
    family has a typed Python object model or a Pure Python layout.  The source
    remains mutable and is compiled verbatim by the Official backend.
    """

    kind: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def elements(self) -> Iterable[SemanticElement]:
        return ()

    def validate(self) -> None:
        if not self.kind:
            raise DiagramError("Mermaid source diagram kind must not be empty")
        if not self.source.strip():
            raise DiagramError("Mermaid source must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "model_type": "mermaid-source",
            "source": self.source,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> MermaidSourceDiagram:
        diagram = cls(
            kind=str(value["kind"]),
            source=str(value.get("source", "")),
            metadata=dict(value.get("metadata", {})),
        )
        diagram.validate()
        return diagram


def _style(value: Mapping[str, Any] | ElementStyle | None) -> ElementStyle:
    return ElementStyle.from_dict(value)


def _classes(value: Iterable[str] | None) -> set[str]:
    return set(value or ())


# ---------------------------------------------------------------------------
# Flow diagrams


@dataclass(slots=True)
class FlowNode:
    """Mutable flowchart node addressable by its Mermaid ID."""

    id: str
    label: str
    shape: NodeShape = NodeShape.RECTANGLE
    style: ElementStyle = field(default_factory=ElementStyle)
    metadata: dict[str, Any] = field(default_factory=dict)
    group_id: str | None = None
    classes: set[str] = field(default_factory=set)
    role: str = "node.default"

    def __post_init__(self) -> None:
        self.shape = NodeShape(self.shape)
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        if self.shape == NodeShape.DIAMOND and self.role == "node.default":
            self.role = "node.decision"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "shape": self.shape.value,
            "role": self.role,
            "classes": sorted(self.classes),
            "style": self.style.to_dict(),
            "metadata": dict(self.metadata),
            "group_id": self.group_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FlowNode:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", value["id"])),
            shape=NodeShape(value.get("shape", NodeShape.RECTANGLE.value)),
            role=str(value.get("role", "node.default")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            group_id=value.get("group_id"),
        )


@dataclass(slots=True)
class FlowEdge:
    """Directed or undirected flowchart relationship between two nodes."""

    source: str
    target: str
    label: str | None = None
    directed: bool = True
    style: ElementStyle = field(default_factory=ElementStyle)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
    classes: set[str] = field(default_factory=set)
    role: str = "edge.default"
    start_marker: str | None = None
    end_marker: str | None = "arrow"

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        if not self.directed:
            self.end_marker = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "directed": self.directed,
            "role": self.role,
            "classes": sorted(self.classes),
            "style": self.style.to_dict(),
            "metadata": dict(self.metadata),
            "start_marker": self.start_marker,
            "end_marker": self.end_marker,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FlowEdge:
        return cls(
            source=str(value["source"]),
            target=str(value["target"]),
            label=value.get("label"),
            directed=bool(value.get("directed", True)),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            id=str(value.get("id", "")),
            classes=_classes(value.get("classes")),
            role=str(value.get("role", "edge.default")),
            start_marker=value.get("start_marker"),
            end_marker=value.get("end_marker", "arrow"),
        )


@dataclass(slots=True)
class FlowGroup:
    """Visual Mermaid subgraph containing nodes and child subgraphs."""

    id: str
    label: str
    node_ids: list[str] = field(default_factory=list)
    parent_id: str | None = None
    style: ElementStyle = field(default_factory=ElementStyle)
    metadata: dict[str, Any] = field(default_factory=dict)
    classes: set[str] = field(default_factory=set)
    role: str = "group.default"

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "node_ids": list(self.node_ids),
            "parent_id": self.parent_id,
            "role": self.role,
            "classes": sorted(self.classes),
            "style": self.style.to_dict(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FlowGroup:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", value["id"])),
            node_ids=[str(item) for item in value.get("node_ids", [])],
            parent_id=value.get("parent_id"),
            role=str(value.get("role", "group.default")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(slots=True)
class FlowDiagram(SelectableDiagram):
    """Mutable typed flowchart model with insertion-ordered elements."""

    nodes: dict[str, FlowNode] = field(default_factory=dict)
    edges: list[FlowEdge] = field(default_factory=list)
    groups: dict[str, FlowGroup] = field(default_factory=dict)
    direction: str = "LR"
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: str = field(default="flowchart", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, dict):
            self.nodes = {node.id: node for node in self.nodes}
        if not isinstance(self.groups, dict):
            self.groups = {group.id: group for group in self.groups}
        for index, edge in enumerate(self.edges):
            if not edge.id:
                edge.id = f"edge-{index}"

    def elements(self) -> Iterable[Any]:
        return [*self.groups.values(), *self.edges, *self.nodes.values()]

    def node_map(self) -> dict[str, FlowNode]:
        return self.nodes

    def validate(self) -> None:
        direction = self.direction.upper().replace("TD", "TB")
        if direction not in {"LR", "RL", "TB", "BT"}:
            raise DiagramError(f"Unsupported direction: {self.direction!r}")
        self.direction = direction
        if any(not node_id for node_id in self.nodes):
            raise DiagramError("Node ids must not be empty")
        for edge in self.edges:
            missing = {edge.source, edge.target} - set(self.nodes)
            if missing:
                raise DiagramError(
                    f"Edge {edge.source!r} -> {edge.target!r} references unknown nodes: "
                    f"{', '.join(sorted(missing))}"
                )
        for group in self.groups.values():
            unknown = set(group.node_ids) - set(self.nodes)
            if unknown:
                raise DiagramError(
                    f"Group {group.id!r} references unknown nodes: {', '.join(sorted(unknown))}"
                )
            if group.parent_id is not None and group.parent_id not in self.groups:
                raise DiagramError(
                    f"Group {group.id!r} references unknown parent {group.parent_id!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "direction": self.direction,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "groups": [group.to_dict() for group in self.groups.values()],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FlowDiagram:
        diagram = cls(
            nodes={
                node.id: node
                for node in (FlowNode.from_dict(item) for item in value.get("nodes", []))
            },
            edges=[FlowEdge.from_dict(item) for item in value.get("edges", [])],
            groups={
                group.id: group
                for group in (FlowGroup.from_dict(item) for item in value.get("groups", []))
            },
            direction=str(value.get("direction", "LR")),
            metadata=dict(value.get("metadata", {})),
        )
        diagram.validate()
        return diagram


# ---------------------------------------------------------------------------
# Sequence diagrams


@dataclass(slots=True)
class SequenceParticipant(SemanticElement):
    """Participant or actor occupying one sequence-diagram lifeline."""

    kind: str = "participant"

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or f"sequence.{self.kind}"

    def to_dict(self) -> dict[str, Any]:
        return {**self._base_dict(), "kind": self.kind}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SequenceParticipant:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", value["id"])),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            kind=str(value.get("kind", "participant")),
        )


@dataclass(slots=True)
class SequenceEvent(SemanticElement):
    """Ordered sequence message, note, activation, or fragment event."""

    kind: str = "message"
    source: str | None = None
    target: str | None = None
    message_type: str = "solid"
    placement: str = "over"
    participants: list[str] = field(default_factory=list)
    fragment_type: str | None = None

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or f"sequence.{self.kind}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._base_dict(),
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
            "message_type": self.message_type,
            "placement": self.placement,
            "participants": list(self.participants),
            "fragment_type": self.fragment_type,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SequenceEvent:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", "")),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            kind=str(value.get("kind", "message")),
            source=value.get("source"),
            target=value.get("target"),
            message_type=str(value.get("message_type", "solid")),
            placement=str(value.get("placement", "over")),
            participants=[str(item) for item in value.get("participants", [])],
            fragment_type=value.get("fragment_type"),
        )


@dataclass(slots=True)
class SequenceDiagram(SelectableDiagram):
    """Mutable typed sequence model with participants and ordered events."""

    participants: dict[str, SequenceParticipant] = field(default_factory=dict)
    events: list[SequenceEvent] = field(default_factory=list)
    autonumber: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: str = field(default="sequence", init=False)

    def elements(self) -> Iterable[SemanticElement]:
        return [*self.participants.values(), *self.events]

    def validate(self) -> None:
        known = set(self.participants)
        for event in self.events:
            referenced = {item for item in (event.source, event.target) if item}
            referenced.update(event.participants)
            missing = referenced - known
            if missing:
                raise DiagramError(
                    f"Sequence event {event.id!r} references unknown participants: "
                    f"{', '.join(sorted(missing))}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "participants": [item.to_dict() for item in self.participants.values()],
            "events": [item.to_dict() for item in self.events],
            "autonumber": self.autonumber,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SequenceDiagram:
        diagram = cls(
            participants={
                item.id: item
                for item in (
                    SequenceParticipant.from_dict(row) for row in value.get("participants", [])
                )
            },
            events=[SequenceEvent.from_dict(row) for row in value.get("events", [])],
            autonumber=bool(value.get("autonumber", False)),
            metadata=dict(value.get("metadata", {})),
        )
        diagram.validate()
        return diagram


# ---------------------------------------------------------------------------
# Class diagrams


@dataclass(slots=True)
class ClassNode(SemanticElement):
    """Class or interface with attributes, methods, and stereotypes."""

    attributes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    stereotype: str | None = None
    namespace: str | None = None

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or "class.entity"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._base_dict(),
            "attributes": list(self.attributes),
            "methods": list(self.methods),
            "stereotype": self.stereotype,
            "namespace": self.namespace,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ClassNode:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", value["id"])),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            attributes=[str(item) for item in value.get("attributes", [])],
            methods=[str(item) for item in value.get("methods", [])],
            stereotype=value.get("stereotype"),
            namespace=value.get("namespace"),
        )


@dataclass(slots=True)
class ClassRelationship(SemanticElement):
    """Typed relationship between two class-diagram nodes."""

    source: str = ""
    target: str = ""
    kind: str = "association"
    source_cardinality: str | None = None
    target_cardinality: str | None = None

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or f"class.relationship.{self.kind}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._base_dict(),
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "source_cardinality": self.source_cardinality,
            "target_cardinality": self.target_cardinality,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ClassRelationship:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", "")),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            source=str(value["source"]),
            target=str(value["target"]),
            kind=str(value.get("kind", "association")),
            source_cardinality=value.get("source_cardinality"),
            target_cardinality=value.get("target_cardinality"),
        )


@dataclass(slots=True)
class ClassDiagram(SelectableDiagram):
    """Mutable typed class-diagram model."""

    classes: dict[str, ClassNode] = field(default_factory=dict)
    relationships: list[ClassRelationship] = field(default_factory=list)
    notes: list[SequenceEvent] = field(default_factory=list)
    direction: str = "TB"
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: str = field(default="class", init=False)

    def elements(self) -> Iterable[SemanticElement]:
        return [*self.relationships, *self.classes.values(), *self.notes]

    def validate(self) -> None:
        known = set(self.classes)
        for relationship in self.relationships:
            missing = {relationship.source, relationship.target} - known
            if missing:
                raise DiagramError(
                    f"Class relationship {relationship.id!r} references unknown classes: "
                    f"{', '.join(sorted(missing))}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "direction": self.direction,
            "classes": [item.to_dict() for item in self.classes.values()],
            "relationships": [item.to_dict() for item in self.relationships],
            "notes": [item.to_dict() for item in self.notes],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ClassDiagram:
        diagram = cls(
            classes={
                item.id: item
                for item in (ClassNode.from_dict(row) for row in value.get("classes", []))
            },
            relationships=[
                ClassRelationship.from_dict(row) for row in value.get("relationships", [])
            ],
            notes=[SequenceEvent.from_dict(row) for row in value.get("notes", [])],
            direction=str(value.get("direction", "TB")),
            metadata=dict(value.get("metadata", {})),
        )
        diagram.validate()
        return diagram


# ---------------------------------------------------------------------------
# Entity-relationship diagrams


@dataclass(slots=True)
class ERAttribute:
    """Entity attribute with optional type and PK/FK/UK key markers."""

    type: str
    name: str
    keys: list[str] = field(default_factory=list)
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "keys": list(self.keys),
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ERAttribute:
        return cls(
            type=str(value.get("type", "")),
            name=str(value["name"]),
            keys=[str(item) for item in value.get("keys", [])],
            comment=value.get("comment"),
        )


@dataclass(slots=True)
class EREntity(SemanticElement):
    """Entity and its ordered attributes in an ER diagram."""

    attributes: list[ERAttribute] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or "er.entity"

    def to_dict(self) -> dict[str, Any]:
        return {**self._base_dict(), "attributes": [item.to_dict() for item in self.attributes]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EREntity:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", value["id"])),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            attributes=[ERAttribute.from_dict(row) for row in value.get("attributes", [])],
        )


@dataclass(slots=True)
class ERRelationship(SemanticElement):
    """Labeled ER relationship with source and target cardinalities."""

    source: str = ""
    target: str = ""
    source_cardinality: str = "one"
    target_cardinality: str = "many"
    identifying: bool = True

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or "er.relationship"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._base_dict(),
            "source": self.source,
            "target": self.target,
            "source_cardinality": self.source_cardinality,
            "target_cardinality": self.target_cardinality,
            "identifying": self.identifying,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ERRelationship:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", "")),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            source=str(value["source"]),
            target=str(value["target"]),
            source_cardinality=str(value.get("source_cardinality", "one")),
            target_cardinality=str(value.get("target_cardinality", "many")),
            identifying=bool(value.get("identifying", True)),
        )


@dataclass(slots=True)
class EntityRelationshipDiagram(SelectableDiagram):
    """Mutable typed entity-relationship model."""

    entities: dict[str, EREntity] = field(default_factory=dict)
    relationships: list[ERRelationship] = field(default_factory=list)
    direction: str = "LR"
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: str = field(default="er", init=False)

    def elements(self) -> Iterable[SemanticElement]:
        return [*self.relationships, *self.entities.values()]

    def validate(self) -> None:
        known = set(self.entities)
        for relationship in self.relationships:
            missing = {relationship.source, relationship.target} - known
            if missing:
                raise DiagramError(
                    f"ER relationship {relationship.id!r} references unknown entities: "
                    f"{', '.join(sorted(missing))}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "direction": self.direction,
            "entities": [item.to_dict() for item in self.entities.values()],
            "relationships": [item.to_dict() for item in self.relationships],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EntityRelationshipDiagram:
        diagram = cls(
            entities={
                item.id: item
                for item in (EREntity.from_dict(row) for row in value.get("entities", []))
            },
            relationships=[ERRelationship.from_dict(row) for row in value.get("relationships", [])],
            direction=str(value.get("direction", "LR")),
            metadata=dict(value.get("metadata", {})),
        )
        diagram.validate()
        return diagram


# ---------------------------------------------------------------------------
# State diagrams


@dataclass(slots=True)
class StateNode(SemanticElement):
    """Simple, composite, or pseudo-state in a state diagram."""

    kind: str = "state"
    parent_id: str | None = None

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or f"state.{self.kind}"

    def to_dict(self) -> dict[str, Any]:
        return {**self._base_dict(), "kind": self.kind, "parent_id": self.parent_id}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StateNode:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", value["id"])),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            kind=str(value.get("kind", "state")),
            parent_id=value.get("parent_id"),
        )


@dataclass(slots=True)
class StateTransition(SemanticElement):
    """Directed transition between two states."""

    source: str = ""
    target: str = ""

    def __post_init__(self) -> None:
        self.style = _style(self.style)
        self.classes = _classes(self.classes)
        self.role = self.role or "state.transition"

    def to_dict(self) -> dict[str, Any]:
        return {**self._base_dict(), "source": self.source, "target": self.target}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StateTransition:
        return cls(
            id=str(value["id"]),
            label=str(value.get("label", "")),
            role=str(value.get("role", "")),
            classes=_classes(value.get("classes")),
            style=_style(value.get("style")),
            metadata=dict(value.get("metadata", {})),
            source=str(value["source"]),
            target=str(value["target"]),
        )


@dataclass(slots=True)
class StateDiagram(SelectableDiagram):
    """Mutable typed state-diagram model."""

    states: dict[str, StateNode] = field(default_factory=dict)
    transitions: list[StateTransition] = field(default_factory=list)
    direction: str = "TB"
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: str = field(default="state", init=False)

    def elements(self) -> Iterable[SemanticElement]:
        return [*self.transitions, *self.states.values()]

    def validate(self) -> None:
        known = set(self.states)
        for state in self.states.values():
            if state.parent_id is not None and state.parent_id not in known:
                raise DiagramError(
                    f"State {state.id!r} references unknown parent {state.parent_id!r}"
                )
        for transition in self.transitions:
            missing = {transition.source, transition.target} - known
            if missing:
                raise DiagramError(
                    f"State transition {transition.id!r} references unknown states: "
                    f"{', '.join(sorted(missing))}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind,
            "direction": self.direction,
            "states": [item.to_dict() for item in self.states.values()],
            "transitions": [item.to_dict() for item in self.transitions],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StateDiagram:
        diagram = cls(
            states={
                item.id: item
                for item in (StateNode.from_dict(row) for row in value.get("states", []))
            },
            transitions=[StateTransition.from_dict(row) for row in value.get("transitions", [])],
            direction=str(value.get("direction", "TB")),
            metadata=dict(value.get("metadata", {})),
        )
        diagram.validate()
        return diagram


SemanticDiagram = (
    FlowDiagram
    | SequenceDiagram
    | ClassDiagram
    | EntityRelationshipDiagram
    | StateDiagram
    | MermaidSourceDiagram
)


def diagram_from_dict(value: Mapping[str, Any]) -> SemanticDiagram:
    """Restore a typed semantic root from a versioned JSON-like mapping.

    Args:
        value: Mapping containing ``schema_version``, ``kind``, and the
            family-specific model fields produced by ``to_dict()``.

    Returns:
        A typed semantic root, or a lossless Mermaid source model for a family
        that currently requires the Official backend.

    Raises:
        ValueError: If the schema version or diagram kind is unsupported.
    """

    if int(value.get("schema_version", 1)) != 1:
        raise ValueError(f"Unsupported diagram schema_version: {value.get('schema_version')}")
    kind = str(value.get("kind", "flowchart"))
    factories = {
        "flowchart": FlowDiagram.from_dict,
        "sequence": SequenceDiagram.from_dict,
        "class": ClassDiagram.from_dict,
        "er": EntityRelationshipDiagram.from_dict,
        "state": StateDiagram.from_dict,
    }
    if value.get("model_type") == "mermaid-source":
        return MermaidSourceDiagram.from_dict(value)
    from .mermaid_registry import MERMAID_SOURCE_ONLY_KINDS

    if kind in MERMAID_SOURCE_ONLY_KINDS and "source" in value:
        return MermaidSourceDiagram.from_dict(value)
    try:
        return factories[kind](value)
    except KeyError as exc:
        raise ValueError(f"Unsupported diagram kind: {kind!r}") from exc


@dataclass(slots=True)
class MermaidDocument:
    """Parsed Mermaid source and its mutable typed semantic representation.

    Structural mutations are tracked with a semantic fingerprint. If parsing
    preserved unsupported statements, mutating the partial model is rejected
    at compile time to prevent silent loss of the unknown source.
    """

    source: str
    model: SemanticDiagram
    diagnostics: list[Diagnostic] = field(default_factory=list)
    raw_statements: list[str] = field(default_factory=list)
    is_fully_modeled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    _initial_fingerprint: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        self._initial_fingerprint = self.model_fingerprint()

    def model_fingerprint(self) -> str:
        payload = json.dumps(
            self.model.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @property
    def model_changed(self) -> bool:
        return self.model_fingerprint() != self._initial_fingerprint

    @property
    def modeling_rate(self) -> float:
        """Approximate modeled coverage using semantic items and raw statements."""

        if isinstance(self.model, MermaidSourceDiagram):
            return 0.0
        modeled = len(list(self.model.elements()))
        total = modeled + len(self.raw_statements)
        return 1.0 if total == 0 else modeled / total

    @property
    def required_backend(self) -> str:
        if isinstance(self.model, MermaidSourceDiagram):
            return "official"
        return "native-or-official" if self.is_fully_modeled else "official"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "source": self.source,
            "model": self.model.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "raw_statements": list(self.raw_statements),
            "is_fully_modeled": self.is_fully_modeled,
            "modeling_rate": self.modeling_rate,
            "required_backend": self.required_backend,
            "metadata": dict(self.metadata),
        }

    def save(self, path: str | Path, **options: Any) -> Any:
        """Save this parsed document as SVG, PNG, or JPEG.

        Examples:
            ``document.save("diagram.svg")``
            ``document.save("diagram.png", dpi=600)``
        """

        from .export import save_diagram

        return save_diagram(self, path, **options)

    def to_svg(self, **options: Any) -> str:
        """Return this document as self-contained SVG text."""

        from .export import to_svg

        return to_svg(self, **options)

    def to_png(self, **options: Any) -> bytes:
        """Return PNG bytes; install ``diagram-pptx[image]`` first."""

        from .export import to_png

        return to_png(self, **options)

    def to_jpeg(self, **options: Any) -> bytes:
        """Return JPEG bytes; install ``diagram-pptx[image]`` first."""

        from .export import to_jpeg

        return to_jpeg(self, **options)


# ---------------------------------------------------------------------------
# Temporary compatibility types used by the existing layered flow layout.

DiagramNode = FlowNode
DiagramEdge = FlowEdge
DiagramGroup = FlowGroup
Diagram = FlowDiagram


@dataclass(slots=True)
class PositionedNode:
    node: FlowNode
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
    edge: FlowEdge
    points: list[Point]


@dataclass(slots=True)
class PositionedGroup:
    group: FlowGroup
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
