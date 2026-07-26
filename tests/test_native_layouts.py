import pytest
from test_mermaid_frontend import SAMPLES

from diagram_pptx import parse_mermaid, serialize_mermaid
from diagram_pptx.layout import layout_native
from diagram_pptx.scene import SceneConnector, SceneContainer, SceneShape, SceneText


@pytest.mark.parametrize("kind", list(SAMPLES))
def test_native_layout_is_deterministic_and_complete(kind: str) -> None:
    model = parse_mermaid(SAMPLES[kind]).model
    first = layout_native(model)
    second = layout_native(model)

    assert first == second
    assert first.width > 0
    assert first.height > 0
    assert first.elements
    for element in first.elements:
        if isinstance(element, (SceneShape, SceneContainer)):
            assert element.box.x >= 0
            assert element.box.y >= 0
            assert element.box.x + element.box.width <= first.width + 1e-9
            assert element.box.y + element.box.height <= first.height + 1e-9
        elif isinstance(element, SceneConnector):
            assert len(element.points) >= 2


def test_state_composite_transitions_and_note_are_not_dropped() -> None:
    document = parse_mermaid(SAMPLES["state"])
    scene = layout_native(document.model)
    semantic_ids = {element.semantic_id for element in scene.elements}

    assert "Running" in semantic_ids
    assert "note-0" in semantic_ids
    assert {item.id for item in document.model.transitions} <= semantic_ids


def test_sequence_numbers_only_messages_and_routes_self_calls() -> None:
    scene = layout_native(
        parse_mermaid(
            """
            sequenceDiagram
                autonumber
                participant A
                participant B
                A->>A: Prepare
                alt Ready
                    A->>B: Send
                else Retry
                    B-->>A: Wait
                end
            """
        ).model
    )
    messages = [
        element
        for element in scene.elements
        if isinstance(element, SceneConnector) and element.role == "sequence.message"
    ]
    fragment = next(
        element
        for element in scene.elements
        if isinstance(element, SceneContainer) and element.role == "sequence.fragment.alt"
    )

    assert [message.label for message in messages] == [
        "1. Prepare",
        "2. Send",
        "3. Wait",
    ]
    assert len(messages[0].points) == 4
    assert len(set(messages[0].points)) == 4
    assert all(
        message.metadata["label_point"][1] == pytest.approx(message.points[0].y)
        for message in messages
    )
    assert messages[0].style.dash is None
    assert messages[2].style.dash == "dash"
    assert fragment.label == "alt [Ready]"
    assert fragment.metadata["shape"] == "rectangle"


def test_sequence_actor_is_composite_and_activations_span_nested_durations() -> None:
    document = parse_mermaid(
        """
        sequenceDiagram
            actor User
            participant API
            User->>+API: First
            activate API
            API->>API: Nested work
            deactivate API
            API-->>-User: Done
        """
    )
    reparsed = parse_mermaid(serialize_mermaid(document.model))
    assert reparsed.model == document.model

    scene = layout_native(document.model)
    actor_parts = [
        item
        for item in scene.elements
        if item.semantic_id == "User"
        and isinstance(item, (SceneShape, SceneConnector, SceneText))
        and item.metadata.get("composite_group") == "sequence-actor:User"
    ]
    activations = [
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.role == "sequence.activation"
    ]

    assert len(actor_parts) == 6
    assert len(activations) == 2
    assert {item.metadata["activation_depth"] for item in activations} == {0, 1}
    assert max(item.box.height for item in activations) > min(
        item.box.height for item in activations
    )
    depth_zero = next(item for item in activations if item.metadata["activation_depth"] == 0)
    depth_one = next(item for item in activations if item.metadata["activation_depth"] == 1)
    assert depth_one.box.x > depth_zero.box.x


def test_class_namespace_is_a_visual_container_and_round_trips() -> None:
    document = parse_mermaid(
        """
        classDiagram
            direction LR
            namespace Domain {
                class Order
                class Customer
            }
            Customer --> Order
        """
    )
    reparsed = parse_mermaid(serialize_mermaid(document.model))
    assert reparsed.model == document.model

    scene = layout_native(document.model)
    namespace = next(
        item
        for item in scene.elements
        if isinstance(item, SceneContainer) and item.role == "class.namespace"
    )
    members = [
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.semantic_id in {"Order", "Customer"}
    ]

    assert namespace.label == "Domain"
    assert all(namespace.box.x <= item.box.x for item in members)
    assert all(namespace.box.y <= item.box.y for item in members)
    assert all(
        namespace.box.x + namespace.box.width >= item.box.x + item.box.width for item in members
    )
    assert all(
        namespace.box.y + namespace.box.height >= item.box.y + item.box.height for item in members
    )


def test_class_association_preserves_an_explicit_arrowhead() -> None:
    scene = layout_native(
        parse_mermaid(
            """
            classDiagram
                A --> B
                B -- C
            """
        ).model
    )
    relationships = [
        item
        for item in scene.elements
        if isinstance(item, SceneConnector) and item.role.startswith("class.relationship")
    ]

    assert relationships[0].end_marker == "arrow"
    assert relationships[1].end_marker is None


def test_state_start_and_end_use_filled_dot_and_bullseye_parts() -> None:
    scene = layout_native(
        parse_mermaid(
            """
            stateDiagram-v2
                [*] --> Working
                Working --> [*]
            """
        ).model
    )
    start = next(
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.role == "state.start"
    )
    end_parts = [
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.role.startswith("state.end")
    ]

    assert start.shape == "ellipse"
    assert {item.role for item in end_parts} == {"state.end", "state.end.inner"}
    outer = next(item for item in end_parts if item.role == "state.end")
    inner = next(item for item in end_parts if item.role == "state.end.inner")
    assert inner.box.x > outer.box.x
    assert inner.box.y > outer.box.y


def test_composite_state_transitions_use_container_boundary() -> None:
    document = parse_mermaid(
        """
        stateDiagram-v2
            direction LR
            state Workflow {
                [*] --> Idle
                Idle --> Busy
            }
            Outside --> Workflow : enter
            Workflow --> Outside : leave
            Workflow --> Done : finish
        """
    )
    scene = layout_native(document.model)
    container = next(
        item
        for item in scene.elements
        if isinstance(item, SceneContainer) and item.semantic_id == "Workflow"
    )
    incoming = next(
        item
        for item in scene.elements
        if isinstance(item, SceneConnector) and item.target_id == "Workflow"
    )
    outgoing = next(
        item
        for item in scene.elements
        if isinstance(item, SceneConnector) and item.source_id == "Workflow"
    )
    outside = next(
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.semantic_id == "Outside"
    )
    done = next(
        item
        for item in scene.elements
        if isinstance(item, SceneShape) and item.semantic_id == "Done"
    )

    def on_boundary(point: object) -> bool:
        return (
            point.x == pytest.approx(container.box.x)
            or point.x == pytest.approx(container.box.x + container.box.width)
            or point.y == pytest.approx(container.box.y)
            or point.y == pytest.approx(container.box.y + container.box.height)
        )

    assert on_boundary(incoming.points[-1])
    assert on_boundary(outgoing.points[0])
    assert outside.box.x + outside.box.width < container.box.x
    assert done.box.x > container.box.x + container.box.width
    assert container.metadata["composite_group"] == "state-composite:Workflow"
