"""Deterministic Pure Python layouts for the five semantic diagram families."""

from __future__ import annotations

from collections.abc import Callable

from ..model import (
    ClassDiagram,
    EntityRelationshipDiagram,
    FlowDiagram,
    FlowEdge,
    FlowGroup,
    FlowNode,
    NodeShape,
    SemanticDiagram,
    SequenceDiagram,
    StateDiagram,
)
from ..scene import (
    Box,
    DrawingScene,
    Point,
    SceneConnector,
    SceneContainer,
    SceneShape,
    SceneText,
)
from ..styles import ElementStyle
from .layered import LayeredLayout


def layout_native(model: SemanticDiagram) -> DrawingScene:
    """Return a deterministic positioned scene for any supported model."""

    if isinstance(model, FlowDiagram):
        scene = _layout_flow(model)
    elif isinstance(model, SequenceDiagram):
        scene = _layout_sequence(model)
    elif isinstance(model, ClassDiagram):
        scene = _layout_class(model)
    elif isinstance(model, EntityRelationshipDiagram):
        scene = _layout_er(model)
    elif isinstance(model, StateDiagram):
        scene = _layout_state(model)
    else:
        raise TypeError(f"Unsupported semantic model: {type(model).__name__}")
    scene.metadata.setdefault("coordinate_units", "inches")
    return scene


def _layout_flow(model: FlowDiagram) -> DrawingScene:
    layout = LayeredLayout().apply(model)
    scene = DrawingScene(
        kind=model.kind,
        width=layout.width,
        height=layout.height,
        metadata={"layout_engine": "native-layered"},
    )
    for positioned in layout.groups:
        group = positioned.group
        scene.add(
            SceneContainer(
                id=f"group:{group.id}",
                semantic_id=group.id,
                role=group.role,
                classes=set(group.classes),
                style=group.style.copy(),
                z_index=0,
                box=Box(
                    positioned.x,
                    positioned.y,
                    positioned.width,
                    positioned.height,
                ),
                label=group.label,
                metadata=dict(group.metadata),
            )
        )
    for routed in layout.edges:
        edge = routed.edge
        scene.add(
            SceneConnector(
                id=f"edge:{edge.id}",
                semantic_id=edge.id,
                role=edge.role,
                classes=set(edge.classes),
                style=edge.style.copy(),
                z_index=10,
                points=list(routed.points),
                source_id=edge.source,
                target_id=edge.target,
                directed=edge.directed,
                start_marker=edge.start_marker,
                end_marker=edge.end_marker,
                label=edge.label,
                metadata={**edge.metadata, "bind": edge.metadata.get("bind", True)},
            )
        )
    for positioned in layout.nodes:
        node = positioned.node
        scene.add(
            SceneShape(
                id=f"node:{node.id}",
                semantic_id=node.id,
                role=node.role,
                classes=set(node.classes),
                style=node.style.copy(),
                z_index=20,
                box=Box(positioned.x, positioned.y, positioned.width, positioned.height),
                shape=node.shape.value,
                text=node.label,
                metadata=dict(node.metadata),
            )
        )
    scene.recompute_extents(padding=0.05)
    return scene


def _layout_sequence(model: SequenceDiagram) -> DrawingScene:
    participant_width = 2.0
    participant_height = 0.9
    column_gap = 1.2
    row_height = 0.68
    margin = 0.35
    participants = list(model.participants.values())
    centers = {
        participant.id: margin + participant_width / 2 + index * (participant_width + column_gap)
        for index, participant in enumerate(participants)
    }
    event_top = 1.45
    diagram_bottom = event_top + max(1, len(model.events)) * row_height + 0.6
    scene = DrawingScene(
        kind=model.kind,
        width=max(
            3.0,
            len(participants) * (participant_width + column_gap) - column_gap + 2 * margin,
        ),
        height=diagram_bottom + participant_height + margin,
        metadata={"layout_engine": "native-sequence"},
    )
    for participant in participants:
        center_x = centers[participant.id]
        scene.add(
            SceneConnector(
                id=f"lifeline:{participant.id}",
                semantic_id=participant.id,
                role="sequence.lifeline",
                style=ElementStyle(line="lifeline", dash="dash", line_width=0.8),
                z_index=5,
                points=[
                    Point(center_x, margin + participant_height),
                    Point(center_x, diagram_bottom),
                ],
                directed=False,
            )
        )
        if participant.kind == "actor":
            _add_sequence_actor(
                scene,
                participant_id=participant.id,
                label=participant.label,
                center_x=center_x,
                top=margin,
                classes=participant.classes,
                style=participant.style,
                metadata=participant.metadata,
            )
        else:
            scene.add(
                SceneShape(
                    id=f"participant:{participant.id}",
                    semantic_id=participant.id,
                    role=participant.role,
                    classes=set(participant.classes),
                    style=participant.style.copy(),
                    z_index=20,
                    box=Box(
                        center_x - participant_width / 2,
                        margin + 0.1,
                        participant_width,
                        0.65,
                    ),
                    shape="rectangle",
                    text=participant.label,
                    metadata=dict(participant.metadata),
                )
            )

    for activation_id, participant_id, start_y, end_y, depth in _sequence_activations(
        model,
        event_top=event_top,
        row_height=row_height,
        diagram_bottom=diagram_bottom,
    ):
        center_x = centers[participant_id]
        scene.add(
            SceneShape(
                id=f"activation:{activation_id}",
                semantic_id=activation_id,
                role="sequence.activation",
                style=ElementStyle(
                    fill="surface",
                    line="edge",
                    line_width=1.0,
                ),
                z_index=15,
                box=Box(
                    center_x - 0.08 + depth * 0.11,
                    start_y,
                    0.16,
                    max(0.28, end_y - start_y),
                ),
                shape="rectangle",
                text="",
                metadata={
                    "participant_id": participant_id,
                    "activation_depth": depth,
                },
            )
        )

    fragment_stack: list[tuple[str, str, str, float]] = []
    message_number = 0
    for index, event in enumerate(model.events):
        y = event_top + index * row_height
        if event.kind == "message" and event.source and event.target:
            source_x = centers[event.source]
            target_x = centers[event.target]
            message_number += 1
            number = f"{message_number}. " if model.autonumber else ""
            message_style = event.style.copy()
            if str(event.metadata.get("arrow", "")).startswith("--") and message_style.dash is None:
                message_style.dash = "dash"
            if event.source == event.target:
                direction = -1 if event.source == participants[-1].id else 1
                loop_x = source_x + direction * 0.58
                points = [
                    Point(source_x, y),
                    Point(loop_x, y),
                    Point(loop_x, y + 0.28),
                    Point(source_x, y + 0.28),
                ]
                label_point = (source_x + direction * 0.29, y)
            else:
                points = [Point(source_x, y), Point(target_x, y)]
                label_point = ((source_x + target_x) / 2, y)
            scene.add(
                SceneConnector(
                    id=f"event:{event.id}",
                    semantic_id=event.id,
                    role=event.role,
                    classes=set(event.classes),
                    style=message_style,
                    z_index=10,
                    points=points,
                    source_id=event.source,
                    target_id=event.target,
                    directed=True,
                    end_marker="arrow",
                    label=f"{number}{event.label}",
                    metadata={
                        **event.metadata,
                        "label_placement": "above",
                        "label_point": label_point,
                    },
                )
            )
        elif event.kind == "note":
            participant_ids = event.participants or [participants[0].id]
            xs = [centers[item] for item in participant_ids]
            width = max(1.6, max(xs) - min(xs) + 1.8)
            center_x = (min(xs) + max(xs)) / 2
            if event.placement == "left of":
                center_x = min(xs) - 1.0
            elif event.placement == "right of":
                center_x = max(xs) + 1.0
            scene.add(
                SceneShape(
                    id=f"event:{event.id}",
                    semantic_id=event.id,
                    role=event.role,
                    classes=set(event.classes),
                    style=event.style.copy(),
                    z_index=25,
                    box=Box(center_x - width / 2, y - 0.25, width, 0.5),
                    shape="rectangle",
                    text=event.label,
                )
            )
        elif event.kind == "fragment_start":
            fragment_stack.append((event.id, event.fragment_type or "fragment", event.label, y))
        elif event.kind == "fragment_else":
            scene.add(
                SceneConnector(
                    id=f"event:{event.id}",
                    semantic_id=event.id,
                    role="sequence.fragment.separator",
                    style=ElementStyle(line="group_line", dash="dash"),
                    z_index=8,
                    points=[Point(margin, y), Point(scene.width - margin, y)],
                    directed=False,
                    label=event.label,
                )
            )
        elif event.kind == "fragment_end" and fragment_stack:
            fragment_id, fragment_type, fragment_label, start_y = fragment_stack.pop()
            label = fragment_type
            if fragment_label:
                label = f"{fragment_type} [{fragment_label}]"
            scene.add(
                SceneContainer(
                    id=f"fragment:{fragment_id}",
                    semantic_id=fragment_id,
                    role=f"sequence.fragment.{fragment_type}",
                    style=ElementStyle(
                        line="group_line",
                        fill="#FFFFFF00",
                        line_width=1.2,
                        dash="solid",
                    ),
                    z_index=7,
                    box=Box(
                        margin,
                        start_y - 0.35,
                        scene.width - 2 * margin,
                        max(row_height, y - start_y + 0.65),
                    ),
                    label=label,
                    metadata={"shape": "rectangle"},
                )
            )
    scene.recompute_extents(padding=0.1)
    return scene


def _add_sequence_actor(
    scene: DrawingScene,
    *,
    participant_id: str,
    label: str,
    center_x: float,
    top: float,
    classes: set[str],
    style: ElementStyle,
    metadata: dict[str, object],
) -> None:
    """Add one editable, grouped stick figure for a Native actor."""

    group_id = f"sequence-actor:{participant_id}"
    composite = {
        **metadata,
        "composite_group": group_id,
        "composite_group_name": f"diagram:sequence:actor:{participant_id}",
    }
    scene.add(
        SceneShape(
            id=f"actor-head:{participant_id}",
            semantic_id=participant_id,
            role="sequence.actor",
            classes=set(classes),
            style=style.copy(),
            z_index=20,
            box=Box(center_x - 0.12, top, 0.24, 0.24),
            shape="ellipse",
            text="",
            metadata=dict(composite),
        )
    )
    line_style = style.copy()
    for part, points in (
        (
            "body",
            [Point(center_x, top + 0.24), Point(center_x, top + 0.52)],
        ),
        (
            "arms",
            [
                Point(center_x - 0.23, top + 0.34),
                Point(center_x, top + 0.29),
                Point(center_x + 0.23, top + 0.34),
            ],
        ),
        (
            "leg-left",
            [Point(center_x, top + 0.52), Point(center_x - 0.2, top + 0.69)],
        ),
        (
            "leg-right",
            [Point(center_x, top + 0.52), Point(center_x + 0.2, top + 0.69)],
        ),
    ):
        scene.add(
            SceneConnector(
                id=f"actor-{part}:{participant_id}",
                semantic_id=participant_id,
                role="sequence.actor",
                classes=set(classes),
                style=line_style.copy(),
                z_index=20,
                points=points,
                directed=False,
                end_marker=None,
                metadata=dict(composite),
            )
        )
    scene.add(
        SceneText(
            id=f"actor-label:{participant_id}",
            semantic_id=participant_id,
            role="sequence.actor",
            classes=set(classes),
            style=style.copy(),
            z_index=20,
            box=Box(center_x - 1.0, top + 0.65, 2.0, 0.25),
            text=label,
            metadata=dict(composite),
        )
    )


def _sequence_activations(
    model: SequenceDiagram,
    *,
    event_top: float,
    row_height: float,
    diagram_bottom: float,
) -> list[tuple[str, str, float, float, int]]:
    """Resolve explicit and inline activation events into duration bars."""

    open_by_participant: dict[str, list[tuple[str, float, int]]] = {
        participant_id: [] for participant_id in model.participants
    }
    intervals: list[tuple[str, str, float, float, int]] = []
    activation_index = 0

    def open_activation(participant_id: str, y: float) -> None:
        nonlocal activation_index
        stack = open_by_participant[participant_id]
        activation_id = f"activation-{participant_id}-{activation_index}"
        activation_index += 1
        stack.append((activation_id, y - 0.08, len(stack)))

    def close_activation(participant_id: str, y: float) -> None:
        stack = open_by_participant[participant_id]
        if not stack:
            return
        activation_id, start_y, depth = stack.pop()
        intervals.append(
            (
                activation_id,
                participant_id,
                start_y,
                max(start_y + 0.28, y + 0.12),
                depth,
            )
        )

    for index, event in enumerate(model.events):
        y = event_top + index * row_height
        inline_activation = event.metadata.get("activation")
        if event.kind == "message" and event.target and inline_activation == "+":
            open_activation(event.target, y)
        elif event.kind == "activate" and event.participants:
            open_activation(event.participants[0], y)

        if event.kind == "message" and event.target and inline_activation == "-":
            close_activation(event.target, y)
        elif event.kind == "deactivate" and event.participants:
            close_activation(event.participants[0], y)

    for participant_id, stack in open_by_participant.items():
        while stack:
            activation_id, start_y, depth = stack.pop()
            intervals.append(
                (
                    activation_id,
                    participant_id,
                    start_y,
                    max(start_y + 0.28, diagram_bottom),
                    depth,
                )
            )
    return intervals


def _graph_family_scene(
    *,
    kind: str,
    direction: str,
    nodes: dict[str, FlowNode],
    edges: list[FlowEdge],
    role_for_node: Callable[[str], str],
) -> DrawingScene:
    flow = FlowDiagram(nodes=nodes, edges=edges, direction=direction)
    scene = _layout_flow(flow)
    scene.kind = kind
    scene.metadata["layout_engine"] = f"native-{kind}-layered"
    for element in scene.elements:
        if isinstance(element, SceneShape):
            element.role = role_for_node(element.semantic_id)
    return scene


def _layout_class(model: ClassDiagram) -> DrawingScene:
    nodes: dict[str, FlowNode] = {}
    for item in model.classes.values():
        parts = []
        if item.stereotype:
            parts.append(f"«{item.stereotype}»")
        parts.append(item.label)
        if item.attributes:
            parts.extend(["────────", *item.attributes])
        if item.methods:
            parts.extend(["────────", *item.methods])
        longest = max((len(part) for part in parts), default=8)
        nodes[item.id] = FlowNode(
            id=item.id,
            label="\n".join(parts),
            shape=NodeShape.RECTANGLE,
            style=item.style.copy(),
            classes=set(item.classes),
            role=item.role,
            metadata={
                **item.metadata,
                "width": min(5.2, max(2.3, 1.0 + longest * 0.105)),
                "height": max(1.0, 0.42 + len(parts) * 0.29),
            },
        )
    edges = [
        FlowEdge(
            id=item.id,
            source=item.source,
            target=item.target,
            label=item.label or None,
            style=item.style.copy(),
            classes=set(item.classes),
            role=item.role,
            metadata={**item.metadata, "relationship_kind": item.kind},
            start_marker=_relationship_start_marker(item.kind),
            end_marker=_relationship_end_marker(
                item.kind,
                token=str(item.metadata.get("token", "")),
            ),
        )
        for item in model.relationships
    ]
    scene = _graph_family_scene(
        kind=model.kind,
        direction=model.direction,
        nodes=nodes,
        edges=edges,
        role_for_node=lambda node_id: model.classes[node_id].role,
    )
    class_shapes = {
        item.semantic_id: item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.semantic_id in model.classes
    }
    namespace_members: dict[str, list[SceneShape]] = {}
    for class_id, node in model.classes.items():
        if node.namespace and class_id in class_shapes:
            namespace_members.setdefault(node.namespace, []).append(class_shapes[class_id])
    for namespace, members in namespace_members.items():
        left = min(item.box.x for item in members) - 0.35
        top = min(item.box.y for item in members) - 0.55
        right = max(item.box.x + item.box.width for item in members) + 0.35
        bottom = max(item.box.y + item.box.height for item in members) + 0.35
        scene.add(
            SceneContainer(
                id=f"namespace:{namespace}",
                semantic_id=f"namespace:{namespace}",
                role="class.namespace",
                z_index=0,
                box=Box(left, top, right - left, bottom - top),
                label=namespace,
                metadata={"namespace": namespace},
            )
        )
    for note in model.notes:
        target = note.participants[0] if note.participants else None
        target_shape = next(
            (
                item
                for item in scene.elements
                if isinstance(item, SceneShape) and item.semantic_id == target
            ),
            None,
        )
        box = (
            Box(
                target_shape.box.x + target_shape.box.width + 0.25,
                target_shape.box.y,
                2.2,
                0.7,
            )
            if target_shape
            else Box(0.1, scene.height + 0.2, 2.2, 0.7)
        )
        scene.add(
            SceneShape(
                id=f"note:{note.id}",
                semantic_id=note.id,
                role="class.note",
                style=note.style.copy(),
                z_index=25,
                box=box,
                shape="rectangle",
                text=note.label,
            )
        )
    scene.recompute_extents(padding=0.1)
    return scene


def _layout_er(model: EntityRelationshipDiagram) -> DrawingScene:
    nodes: dict[str, FlowNode] = {}
    for entity in model.entities.values():
        lines = [entity.label]
        if entity.attributes:
            lines.append("────────")
            for attribute in entity.attributes:
                keys = f" [{','.join(attribute.keys)}]" if attribute.keys else ""
                lines.append(f"{attribute.type} {attribute.name}{keys}")
        longest = max((len(line) for line in lines), default=8)
        nodes[entity.id] = FlowNode(
            id=entity.id,
            label="\n".join(lines),
            shape=NodeShape.RECTANGLE,
            style=entity.style.copy(),
            classes=set(entity.classes),
            role=entity.role,
            metadata={
                **entity.metadata,
                "width": min(5.2, max(2.4, 1.0 + longest * 0.105)),
                "height": max(1.0, 0.45 + len(lines) * 0.29),
            },
        )
    edges = [
        FlowEdge(
            id=item.id,
            source=item.source,
            target=item.target,
            label=item.label or None,
            style=item.style.copy(),
            classes=set(item.classes),
            role=item.role,
            metadata={
                **item.metadata,
                "source_cardinality": item.source_cardinality,
                "target_cardinality": item.target_cardinality,
            },
            start_marker=_cardinality_marker(item.source_cardinality),
            end_marker=_cardinality_marker(item.target_cardinality),
        )
        for item in model.relationships
    ]
    return _graph_family_scene(
        kind=model.kind,
        direction=model.direction,
        nodes=nodes,
        edges=edges,
        role_for_node=lambda node_id: model.entities[node_id].role,
    )


def _layout_state(model: StateDiagram) -> DrawingScene:
    nodes: dict[str, FlowNode] = {}
    groups: dict[str, FlowGroup] = {}
    for state in model.states.values():
        shape = {
            "start": NodeShape.ELLIPSE,
            "end": NodeShape.ELLIPSE,
            "choice": NodeShape.DIAMOND,
            "fork": NodeShape.RECTANGLE,
            "join": NodeShape.RECTANGLE,
        }.get(state.kind, NodeShape.ROUNDED_RECTANGLE)
        metadata = dict(state.metadata)
        if state.kind in {"start", "end"}:
            metadata.update(width=0.35, height=0.35)
        elif state.kind in {"fork", "join"}:
            metadata.update(width=2.0, height=0.18)
        nodes[state.id] = FlowNode(
            id=state.id,
            label=state.label,
            shape=shape,
            style=state.style.copy(),
            classes=set(state.classes),
            role=state.role,
            group_id=state.parent_id,
            metadata=metadata,
        )
    for state in model.states.values():
        if state.kind == "composite" or any(
            child.parent_id == state.id for child in model.states.values()
        ):
            children = [
                child.id
                for child in model.states.values()
                if _state_is_descendant(child.id, state.id, model) and child.kind != "composite"
            ]
            groups[state.id] = FlowGroup(
                id=state.id,
                label=state.label,
                node_ids=children,
                parent_id=state.parent_id,
                style=state.style.copy(),
                classes=set(state.classes),
                role="state.composite",
            )
            # The visual container represents the composite; do not duplicate it as a node.
            nodes.pop(state.id, None)
    endpoint_map = {
        group_id: group.node_ids[0] for group_id, group in groups.items() if group.node_ids
    }
    edges: list[FlowEdge] = []
    original_endpoints: dict[str, tuple[str, str]] = {}
    for item in model.transitions:
        source = item.source if item.source in nodes else endpoint_map.get(item.source)
        target = item.target if item.target in nodes else endpoint_map.get(item.target)
        if source is None or target is None:
            continue
        original_endpoints[item.id] = (item.source, item.target)
        edges.append(
            FlowEdge(
                id=item.id,
                source=source,
                target=target,
                label=item.label or None,
                style=item.style.copy(),
                classes=set(item.classes),
                role=item.role,
            )
        )
    flow = FlowDiagram(
        nodes=nodes,
        edges=edges,
        groups=groups,
        direction=model.direction,
    )
    scene = _layout_flow(flow)
    scene.kind = model.kind
    scene.metadata["layout_engine"] = "native-state-layered"
    containers = {
        item.semantic_id: item for item in scene.elements if isinstance(item, SceneContainer)
    }
    state_shapes = {
        item.semantic_id: item for item in scene.elements if isinstance(item, SceneShape)
    }
    external_placements: dict[str, tuple[SceneContainer, bool]] = {}
    for original_source, original_target in original_endpoints.values():
        if (
            original_source in containers
            and original_target in state_shapes
            and model.states[original_target].parent_id is None
        ):
            external_placements.setdefault(
                original_target,
                (containers[original_source], True),
            )
        if (
            original_target in containers
            and original_source in state_shapes
            and model.states[original_source].parent_id is None
        ):
            # If a state both enters and receives a return transition from a
            # composite, keep it on the entry side and route the return around.
            external_placements[original_source] = (
                containers[original_target],
                False,
            )
    for state_id, (container, after) in external_placements.items():
        _place_state_outside_container(
            state_shapes[state_id],
            container,
            direction=model.direction,
            after=after,
        )

    for element in scene.elements:
        if isinstance(element, SceneConnector) and element.semantic_id in original_endpoints:
            original_source, original_target = original_endpoints[element.semantic_id]
            element.source_id, element.target_id = original_source, original_target
            source = containers.get(original_source) or state_shapes.get(original_source)
            target = containers.get(original_target) or state_shapes.get(original_target)
            if source is not None and target is not None:
                element.points = _route_state_boxes(
                    source.box,
                    target.box,
                    direction=model.direction,
                )

    for composite_id, container in containers.items():
        group_id = f"state-composite:{composite_id}"
        parent_id = model.states[composite_id].parent_id
        container.metadata.update(
            {
                "composite_group": group_id,
                "composite_group_name": f"diagram:state:composite:{composite_id}",
            }
        )
        if parent_id in containers:
            container.metadata["composite_group_parent"] = f"state-composite:{parent_id}"
    for state_id, shape in state_shapes.items():
        parent_id = model.states[state_id].parent_id
        if parent_id in containers:
            shape.metadata["composite_group"] = f"state-composite:{parent_id}"
    for state_id, shape in state_shapes.items():
        if model.states[state_id].kind != "end":
            continue
        inset = min(shape.box.width, shape.box.height) * 0.27
        scene.add(
            SceneShape(
                id=f"state-end-inner:{state_id}",
                semantic_id=state_id,
                role="state.end.inner",
                z_index=21,
                box=Box(
                    shape.box.x + inset,
                    shape.box.y + inset,
                    shape.box.width - 2 * inset,
                    shape.box.height - 2 * inset,
                ),
                shape="ellipse",
                text="",
                metadata={
                    key: value
                    for key, value in shape.metadata.items()
                    if key.startswith("composite_group")
                },
            )
        )
    for element in scene.elements:
        if not isinstance(element, SceneConnector):
            continue
        endpoints = original_endpoints.get(
            element.semantic_id,
            (element.source_id or "", element.target_id or ""),
        )
        group_id = _state_common_composite(*endpoints, model=model)
        if group_id in containers:
            element.metadata["composite_group"] = f"state-composite:{group_id}"
    for note in model.metadata.get("notes", []):
        target = next(
            (
                item
                for item in scene.elements
                if isinstance(item, (SceneShape, SceneContainer))
                and item.semantic_id == note["target"]
            ),
            None,
        )
        if target is None:
            continue
        note_width = 2.0
        note_x = (
            target.box.x - note_width - 0.25
            if note["placement"] == "left"
            else target.box.x + target.box.width + 0.25
        )
        scene.add(
            SceneShape(
                id=f"note:{note['id']}",
                semantic_id=note["id"],
                role="state.note",
                z_index=25,
                box=Box(note_x, target.box.y, note_width, 0.65),
                shape="rectangle",
                text=note["label"],
                metadata=(
                    {
                        "composite_group": (
                            f"state-composite:{model.states[note['target']].parent_id}"
                        )
                    }
                    if note["target"] in model.states
                    and model.states[note["target"]].parent_id in containers
                    else {}
                ),
            )
        )
    scene.recompute_extents(padding=0.1)
    return scene


def _state_is_descendant(
    state_id: str,
    ancestor_id: str,
    model: StateDiagram,
) -> bool:
    parent_id = model.states[state_id].parent_id
    while parent_id is not None:
        if parent_id == ancestor_id:
            return True
        parent = model.states.get(parent_id)
        parent_id = parent.parent_id if parent is not None else None
    return False


def _state_ancestor_chain(state_id: str, model: StateDiagram) -> list[str]:
    chain: list[str] = []
    current = model.states.get(state_id)
    if current is not None and current.kind == "composite":
        chain.append(current.id)
    parent_id = current.parent_id if current is not None else None
    while parent_id is not None:
        chain.append(parent_id)
        parent = model.states.get(parent_id)
        parent_id = parent.parent_id if parent is not None else None
    return chain


def _state_common_composite(
    source_id: str,
    target_id: str,
    *,
    model: StateDiagram,
) -> str | None:
    target_ancestors = set(_state_ancestor_chain(target_id, model))
    return next(
        (
            ancestor
            for ancestor in _state_ancestor_chain(source_id, model)
            if ancestor in target_ancestors
        ),
        None,
    )


def _place_state_outside_container(
    shape: SceneShape,
    container: SceneContainer,
    *,
    direction: str,
    after: bool,
    gap: float = 0.9,
) -> None:
    box = shape.box
    if direction == "LR":
        x = (
            container.box.x + container.box.width + gap
            if after
            else container.box.x - gap - box.width
        )
        y = container.box.center.y - box.height / 2
    elif direction == "RL":
        x = (
            container.box.x - gap - box.width
            if after
            else container.box.x + container.box.width + gap
        )
        y = container.box.center.y - box.height / 2
    elif direction == "TB":
        x = container.box.center.x - box.width / 2
        y = (
            container.box.y + container.box.height + gap
            if after
            else container.box.y - gap - box.height
        )
    else:
        x = container.box.center.x - box.width / 2
        y = (
            container.box.y - gap - box.height
            if after
            else container.box.y + container.box.height + gap
        )
    shape.box = Box(x, y, box.width, box.height)


def _route_state_boxes(
    source: Box,
    target: Box,
    *,
    direction: str,
) -> list[Point]:
    horizontal = direction in {"LR", "RL"}
    if horizontal:
        increasing = target.center.x >= source.center.x
        start = Point(
            source.x + source.width if increasing else source.x,
            source.center.y,
        )
        end = Point(
            target.x if increasing else target.x + target.width,
            target.center.y,
        )
        expected_increasing = direction == "LR"
        if increasing == expected_increasing:
            middle = (start.x + end.x) / 2
            return [start, Point(middle, start.y), Point(middle, end.y), end]
        lane_y = min(source.y, target.y) - 0.55
        return [
            start,
            Point(start.x, lane_y),
            Point(end.x, lane_y),
            end,
        ]

    increasing = target.center.y >= source.center.y
    start = Point(
        source.center.x,
        source.y + source.height if increasing else source.y,
    )
    end = Point(
        target.center.x,
        target.y if increasing else target.y + target.height,
    )
    expected_increasing = direction == "TB"
    if increasing == expected_increasing:
        middle = (start.y + end.y) / 2
        return [start, Point(start.x, middle), Point(end.x, middle), end]
    lane_x = min(source.x, target.x) - 0.55
    return [
        start,
        Point(lane_x, start.y),
        Point(lane_x, end.y),
        end,
    ]


def _relationship_start_marker(kind: str) -> str | None:
    return {"composition": "diamond", "aggregation": "diamond"}.get(kind)


def _relationship_end_marker(kind: str, *, token: str = "") -> str | None:
    return {
        "inheritance": "triangle",
        "realization": "triangle",
        "dependency": "arrow",
        "association": "arrow" if token.rstrip().endswith(">") else None,
    }.get(kind, "arrow")


def _cardinality_marker(cardinality: str) -> str:
    return f"cardinality:{cardinality}"
