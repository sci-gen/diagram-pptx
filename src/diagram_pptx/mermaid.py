"""Mermaid frontend: typed parsing, diagnostics, and canonical serialization."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .diagnostics import Diagnostic, MermaidParseError
from .importers.mermaid import MermaidFlowchartImporter
from .model import (
    ClassDiagram,
    ClassNode,
    ClassRelationship,
    EntityRelationshipDiagram,
    ERAttribute,
    EREntity,
    ERRelationship,
    FlowDiagram,
    MermaidDocument,
    SequenceDiagram,
    SequenceEvent,
    SequenceParticipant,
    StateDiagram,
    StateNode,
    StateTransition,
)

_ID = r"[A-Za-z_][A-Za-z0-9_-]*"


@dataclass(frozen=True, slots=True)
class _Statement:
    line: int
    column: int
    text: str


def _split_semicolons(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    depth = 0
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            current.append(char)
        elif char in "[{(":
            depth += 1
            current.append(char)
        elif char in "]})":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == ";" and depth == 0:
            if "".join(current).strip():
                parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if "".join(current).strip():
        parts.append("".join(current).strip())
    return parts


def _scan(source: str) -> tuple[list[_Statement], list[str], dict[str, str]]:
    statements: list[_Statement] = []
    directives: list[str] = []
    accessibility: dict[str, str] = {}
    for line_number, raw in enumerate(source.replace("\r\n", "\n").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("%%{") and stripped.endswith("}%%"):
            directives.append(stripped)
            continue
        if stripped.startswith("%%"):
            continue
        if stripped.startswith("accTitle:"):
            accessibility["acc_title"] = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("accDescr:"):
            accessibility["acc_description"] = stripped.split(":", 1)[1].strip()
            continue
        for part in _split_semicolons(stripped):
            statements.append(_Statement(line_number, raw.find(part) + 1, part))
    return statements, directives, accessibility


def _unsupported(statement: _Statement, diagnostics: list[Diagnostic]) -> None:
    diagnostics.append(
        Diagnostic(
            code="unsupported-syntax",
            message=f"Statement is preserved for the official backend: {statement.text}",
            line=statement.line,
            column=statement.column,
            statement=statement.text,
        )
    )


def _finish_document(
    source: str,
    model: object,
    diagnostics: list[Diagnostic],
    raw: list[str],
    directives: list[str],
    accessibility: dict[str, str],
    *,
    strict: bool,
) -> MermaidDocument:
    model.metadata.setdefault("directives", directives)  # type: ignore[attr-defined]
    model.metadata.update(accessibility)  # type: ignore[attr-defined]
    model.validate()  # type: ignore[attr-defined]
    if strict and raw:
        first = next(item for item in diagnostics if item.code == "unsupported-syntax")
        location = f"line {first.line}" if first.line else "input"
        raise MermaidParseError(f"Unsupported Mermaid syntax at {location}: {first.statement}")
    return MermaidDocument(
        source=source,
        model=model,  # type: ignore[arg-type]
        diagnostics=diagnostics,
        raw_statements=raw,
        is_fully_modeled=not raw,
    )


def parse_mermaid(source: str, *, strict: bool = False) -> MermaidDocument:
    """Parse Mermaid source into a mutable typed document.

    Args:
        source: Complete Mermaid source for one flowchart, sequence diagram,
            class diagram, ER diagram, or state diagram.
        strict: Raise immediately when any statement cannot be modeled.
            Otherwise unsupported statements are preserved with diagnostics so
            an unchanged document may still use the Official backend.

    Returns:
        A :class:`MermaidDocument` containing the original source, typed model,
        diagnostics, and modeled-coverage information.

    Raises:
        TypeError: If ``source`` is not text.
        MermaidParseError: If the source is empty, has an unsupported diagram
            header, is malformed, or contains unsupported syntax in strict
            mode.
    """

    if not isinstance(source, str):
        raise TypeError("Mermaid source must be text")
    statements, directives, accessibility = _scan(source)
    if not statements:
        raise MermaidParseError("Mermaid source is empty")
    header = statements[0].text.strip().lower()
    if header.startswith(("flowchart ", "graph ")):
        return _parse_flow(source, statements, directives, accessibility, strict=strict)
    if header == "sequencediagram":
        return _parse_sequence(source, statements, directives, accessibility, strict=strict)
    if header.startswith("classdiagram"):
        return _parse_class(source, statements, directives, accessibility, strict=strict)
    if header.startswith("erdiagram"):
        return _parse_er(source, statements, directives, accessibility, strict=strict)
    if header.startswith(("statediagram-v2", "statediagram")):
        return _parse_state(source, statements, directives, accessibility, strict=strict)
    raise MermaidParseError(
        "Supported Mermaid families are flowchart, sequenceDiagram, "
        "classDiagram, erDiagram, and stateDiagram-v2"
    )


def _parse_flow(
    source: str,
    statements: list[_Statement],
    directives: list[str],
    accessibility: dict[str, str],
    *,
    strict: bool,
) -> MermaidDocument:
    diagnostics: list[Diagnostic] = []
    raw: list[str] = []
    try:
        model = MermaidFlowchartImporter().parse(source, tolerant=True)
    except ValueError as exc:
        raise MermaidParseError(str(exc)) from exc
    unsupported = model.metadata.pop("unsupported_statements", [])
    for text in unsupported:
        statement = next(
            (item for item in statements[1:] if item.text == text),
            _Statement(0, 0, text),
        )
        _unsupported(statement, diagnostics)
        raw.append(text)
    return _finish_document(
        source,
        model,
        diagnostics,
        raw,
        directives,
        accessibility,
        strict=strict,
    )


_PARTICIPANT_RE = re.compile(rf"^(participant|actor)\s+({_ID})(?:\s+as\s+(.+))?$", re.IGNORECASE)
_MESSAGE_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_-]*?)\s*([-=]+[)>x]+)\s*([+-]?)\s*"
    rf"({_ID})\s*:\s*(.*)$"
)
_NOTE_RE = re.compile(
    rf"^note\s+(left of|right of|over)\s+({_ID}(?:\s*,\s*{_ID})?)\s*:\s*(.*)$",
    re.IGNORECASE,
)


def _sequence_participant(
    model: SequenceDiagram, participant_id: str, *, kind: str = "participant"
) -> None:
    if participant_id not in model.participants:
        model.participants[participant_id] = SequenceParticipant(
            id=participant_id, label=participant_id, kind=kind
        )


def _parse_sequence(
    source: str,
    statements: list[_Statement],
    directives: list[str],
    accessibility: dict[str, str],
    *,
    strict: bool,
) -> MermaidDocument:
    model = SequenceDiagram()
    diagnostics: list[Diagnostic] = []
    raw: list[str] = []
    event_index = 0
    fragment_stack: list[str] = []
    for statement in statements[1:]:
        text = statement.text.strip()
        lower = text.lower()
        participant = _PARTICIPANT_RE.match(text)
        if participant:
            kind, participant_id, label = participant.groups()
            model.participants[participant_id] = SequenceParticipant(
                id=participant_id,
                label=_strip_quotes(label or participant_id),
                kind=kind.lower(),
            )
            continue
        if lower == "autonumber":
            model.autonumber = True
            continue
        message = _MESSAGE_RE.match(text)
        if message:
            source_id, arrow, activation, target_id, label = message.groups()
            _sequence_participant(model, source_id)
            _sequence_participant(model, target_id)
            model.events.append(
                SequenceEvent(
                    id=f"event-{event_index}",
                    label=label.strip(),
                    kind="message",
                    source=source_id,
                    target=target_id,
                    message_type=_message_type(arrow),
                    metadata={"arrow": arrow, "activation": activation or None},
                )
            )
            event_index += 1
            continue
        note = _NOTE_RE.match(text)
        if note:
            placement, participant_text, label = note.groups()
            participant_ids = [item.strip() for item in participant_text.split(",")]
            for participant_id in participant_ids:
                _sequence_participant(model, participant_id)
            model.events.append(
                SequenceEvent(
                    id=f"event-{event_index}",
                    label=label.strip(),
                    kind="note",
                    placement=placement.lower(),
                    participants=participant_ids,
                )
            )
            event_index += 1
            continue
        activation = re.match(rf"^(activate|deactivate)\s+({_ID})$", text, re.IGNORECASE)
        if activation:
            kind, participant_id = activation.groups()
            _sequence_participant(model, participant_id)
            model.events.append(
                SequenceEvent(
                    id=f"event-{event_index}",
                    kind=kind.lower(),
                    participants=[participant_id],
                )
            )
            event_index += 1
            continue
        fragment = re.match(
            r"^(loop|alt|opt|par|critical|break|rect)\b\s*(.*)$", text, re.IGNORECASE
        )
        if fragment:
            fragment_type, label = fragment.groups()
            fragment_stack.append(fragment_type.lower())
            model.events.append(
                SequenceEvent(
                    id=f"event-{event_index}",
                    label=label.strip(),
                    kind="fragment_start",
                    fragment_type=fragment_type.lower(),
                )
            )
            event_index += 1
            continue
        if lower.startswith(("else", "and", "option")):
            separator = lower.split(maxsplit=1)[0]
            model.events.append(
                SequenceEvent(
                    id=f"event-{event_index}",
                    label=text.split(maxsplit=1)[1] if " " in text else "",
                    kind="fragment_else",
                    fragment_type=fragment_stack[-1] if fragment_stack else None,
                    metadata={"separator": separator},
                )
            )
            event_index += 1
            continue
        if lower == "end":
            if fragment_stack:
                fragment_type = fragment_stack.pop()
                model.events.append(
                    SequenceEvent(
                        id=f"event-{event_index}",
                        kind="fragment_end",
                        fragment_type=fragment_type,
                    )
                )
                event_index += 1
            else:
                _unsupported(statement, diagnostics)
                raw.append(text)
            continue
        _unsupported(statement, diagnostics)
        raw.append(text)
    if fragment_stack:
        raise MermaidParseError(f"Unclosed sequence fragment: {fragment_stack[-1]}")
    return _finish_document(
        source,
        model,
        diagnostics,
        raw,
        directives,
        accessibility,
        strict=strict,
    )


def _message_type(arrow: str) -> str:
    if "x" in arrow:
        return "lost"
    if ")" in arrow:
        return "async"
    if arrow.startswith("--"):
        return "dashed"
    return "solid"


_CLASS_REL_RE = re.compile(
    rf'^({_ID})(?:\s+"([^"]+)")?\s+([<|>*o.()\\/-]+)\s+'
    rf'(?:"([^"]+)"\s+)?({_ID})(?:\s*:\s*(.*))?$'
)


def _class_node(model: ClassDiagram, node_id: str) -> ClassNode:
    return model.classes.setdefault(node_id, ClassNode(id=node_id, label=node_id))


def _parse_class(
    source: str,
    statements: list[_Statement],
    directives: list[str],
    accessibility: dict[str, str],
    *,
    strict: bool,
) -> MermaidDocument:
    model = ClassDiagram()
    diagnostics: list[Diagnostic] = []
    raw: list[str] = []
    active_class: str | None = None
    namespace_stack: list[str] = []
    relationship_index = 0
    note_index = 0
    for statement in statements[1:]:
        text = statement.text.strip()
        lower = text.lower()
        if active_class:
            if text == "}":
                active_class = None
                continue
            node = model.classes[active_class]
            stereotype = re.match(r"^<<(.+)>>$", text)
            if stereotype:
                node.stereotype = stereotype.group(1).strip()
            elif "(" in text and ")" in text:
                node.methods.append(text)
            else:
                node.attributes.append(text)
            continue
        if lower.startswith("direction "):
            model.direction = text.split(maxsplit=1)[1].upper().replace("TD", "TB")
            continue
        namespace = re.match(rf"^namespace\s+({_ID})\s*\{{$", text, re.IGNORECASE)
        if namespace:
            namespace_stack.append(namespace.group(1))
            continue
        if text == "}":
            if namespace_stack:
                namespace_stack.pop()
            else:
                _unsupported(statement, diagnostics)
                raw.append(text)
            continue
        class_match = re.match(
            rf'^class\s+({_ID})(?:\s*\["([^"]+)"\])?\s*(\{{)?$', text, re.IGNORECASE
        )
        if class_match:
            node_id, label, opening = class_match.groups()
            node = _class_node(model, node_id)
            node.label = label or node.label
            node.namespace = namespace_stack[-1] if namespace_stack else None
            if opening:
                active_class = node_id
            continue
        annotation = re.match(rf"^<<(.+)>>\s+({_ID})$", text)
        if annotation:
            stereotype, node_id = annotation.groups()
            _class_node(model, node_id).stereotype = stereotype.strip()
            continue
        relation = _CLASS_REL_RE.match(text)
        if relation:
            source_id, source_card, token, target_card, target_id, label = relation.groups()
            _class_node(model, source_id)
            _class_node(model, target_id)
            model.relationships.append(
                ClassRelationship(
                    id=f"relationship-{relationship_index}",
                    source=source_id,
                    target=target_id,
                    label=(label or "").strip(),
                    kind=_class_relation_kind(token),
                    source_cardinality=source_card,
                    target_cardinality=target_card,
                    metadata={"token": token},
                )
            )
            relationship_index += 1
            continue
        note = re.match(rf'^note(?:\s+for\s+({_ID}))?\s+"(.*)"$', text, re.IGNORECASE)
        if note:
            target_id, label = note.groups()
            if target_id:
                _class_node(model, target_id)
            model.notes.append(
                SequenceEvent(
                    id=f"note-{note_index}",
                    label=label,
                    kind="note",
                    participants=[target_id] if target_id else [],
                )
            )
            note_index += 1
            continue
        member = re.match(rf"^({_ID})\s*:\s*(.+)$", text)
        if member:
            node_id, value = member.groups()
            node = _class_node(model, node_id)
            (node.methods if "(" in value else node.attributes).append(value)
            continue
        _unsupported(statement, diagnostics)
        raw.append(text)
    if active_class:
        raise MermaidParseError(f"Unclosed class body: {active_class}")
    return _finish_document(
        source,
        model,
        diagnostics,
        raw,
        directives,
        accessibility,
        strict=strict,
    )


def _class_relation_kind(token: str) -> str:
    if "<|" in token and ".." in token:
        return "realization"
    if "<|" in token:
        return "inheritance"
    if "*" in token:
        return "composition"
    if "o" in token:
        return "aggregation"
    if ".." in token:
        return "dependency"
    return "association"


_ER_REL_RE = re.compile(rf"^({_ID})\s+([|o}}{{]+)--([|o}}{{]+)\s+({_ID})\s*:\s*(.*)$")


def _er_entity(model: EntityRelationshipDiagram, entity_id: str) -> EREntity:
    return model.entities.setdefault(entity_id, EREntity(id=entity_id, label=entity_id))


def _parse_er(
    source: str,
    statements: list[_Statement],
    directives: list[str],
    accessibility: dict[str, str],
    *,
    strict: bool,
) -> MermaidDocument:
    model = EntityRelationshipDiagram()
    diagnostics: list[Diagnostic] = []
    raw: list[str] = []
    active_entity: str | None = None
    relationship_index = 0
    for statement in statements[1:]:
        text = statement.text.strip()
        lower = text.lower()
        if active_entity:
            if text == "}":
                active_entity = None
                continue
            attribute = _parse_er_attribute(text)
            if attribute is None:
                _unsupported(statement, diagnostics)
                raw.append(text)
            else:
                model.entities[active_entity].attributes.append(attribute)
            continue
        if lower.startswith("direction "):
            model.direction = text.split(maxsplit=1)[1].upper().replace("TD", "TB")
            continue
        entity = re.match(rf"^({_ID})\s*\{{$", text)
        if entity:
            active_entity = entity.group(1)
            _er_entity(model, active_entity)
            continue
        relationship = _ER_REL_RE.match(text)
        if relationship:
            source_id, source_card, target_card, target_id, label = relationship.groups()
            _er_entity(model, source_id)
            _er_entity(model, target_id)
            model.relationships.append(
                ERRelationship(
                    id=f"relationship-{relationship_index}",
                    source=source_id,
                    target=target_id,
                    label=_strip_quotes(label.strip()),
                    source_cardinality=source_card,
                    target_cardinality=target_card,
                    identifying="--" in text,
                )
            )
            relationship_index += 1
            continue
        _unsupported(statement, diagnostics)
        raw.append(text)
    if active_entity:
        raise MermaidParseError(f"Unclosed ER entity: {active_entity}")
    return _finish_document(
        source,
        model,
        diagnostics,
        raw,
        directives,
        accessibility,
        strict=strict,
    )


def _parse_er_attribute(text: str) -> ERAttribute | None:
    match = re.match(
        rf"^(\S+)\s+({_ID})(?:\s+((?:PK|FK|UK)(?:\s*,\s*(?:PK|FK|UK))*))?"
        r'(?:\s+"(.*)")?$',
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    type_name, name, keys, comment = match.groups()
    return ERAttribute(
        type=type_name,
        name=name,
        keys=[item.strip().upper() for item in keys.split(",")] if keys else [],
        comment=comment,
    )


def _state_node(
    model: StateDiagram,
    state_id: str,
    *,
    label: str | None = None,
    kind: str = "state",
    parent_id: str | None = None,
) -> StateNode:
    existing = model.states.get(state_id)
    if existing:
        if label:
            existing.label = label
        if kind != "state":
            existing.kind = kind
            existing.role = f"state.{kind}"
        if parent_id and existing.parent_id is None:
            existing.parent_id = parent_id
        return existing
    state = StateNode(
        id=state_id,
        label=label if label is not None else state_id,
        kind=kind,
        parent_id=parent_id,
    )
    model.states[state_id] = state
    return state


def _parse_state(
    source: str,
    statements: list[_Statement],
    directives: list[str],
    accessibility: dict[str, str],
    *,
    strict: bool,
) -> MermaidDocument:
    model = StateDiagram()
    diagnostics: list[Diagnostic] = []
    raw: list[str] = []
    parent_stack: list[str] = []
    transition_index = 0
    pseudo_counts: dict[tuple[str, str], int] = {}
    note_index = 0
    for statement in statements[1:]:
        text = statement.text.strip()
        lower = text.lower()
        if lower.startswith("direction "):
            model.direction = text.split(maxsplit=1)[1].upper().replace("TD", "TB")
            continue
        if text == "}":
            if parent_stack:
                parent_stack.pop()
            else:
                _unsupported(statement, diagnostics)
                raw.append(text)
            continue
        state = re.match(
            rf'^state\s+(?:"([^"]+)"\s+as\s+)?({_ID})(?:\s+<<([^>]+)>>)?\s*(\{{)?$',
            text,
            re.IGNORECASE,
        )
        if state:
            label, state_id, stereotype, opening = state.groups()
            kind = (stereotype or ("composite" if opening else "state")).lower()
            _state_node(
                model,
                state_id,
                label=label,
                kind=kind,
                parent_id=parent_stack[-1] if parent_stack else None,
            )
            if opening:
                parent_stack.append(state_id)
            continue
        transition = re.match(rf"^(\[\*\]|{_ID})\s*-->\s*(\[\*\]|{_ID})(?:\s*:\s*(.*))?$", text)
        if transition:
            source_id, target_id, label = transition.groups()
            if source_id == "[*]":
                parent_key = parent_stack[-1] if parent_stack else "root"
                counter_key = (parent_key, "start")
                pseudo_index = pseudo_counts.get(counter_key, 0)
                pseudo_counts[counter_key] = pseudo_index + 1
                source_id = f"__start_{parent_key}_{pseudo_index}"
                _state_node(
                    model,
                    source_id,
                    label="",
                    kind="start",
                    parent_id=parent_stack[-1] if parent_stack else None,
                )
            else:
                _state_node(
                    model,
                    source_id,
                    parent_id=parent_stack[-1] if parent_stack else None,
                )
            if target_id == "[*]":
                parent_key = parent_stack[-1] if parent_stack else "root"
                counter_key = (parent_key, "end")
                pseudo_index = pseudo_counts.get(counter_key, 0)
                pseudo_counts[counter_key] = pseudo_index + 1
                target_id = f"__end_{parent_key}_{pseudo_index}"
                _state_node(
                    model,
                    target_id,
                    label="",
                    kind="end",
                    parent_id=parent_stack[-1] if parent_stack else None,
                )
            else:
                _state_node(
                    model,
                    target_id,
                    parent_id=parent_stack[-1] if parent_stack else None,
                )
            model.transitions.append(
                StateTransition(
                    id=f"transition-{transition_index}",
                    source=source_id,
                    target=target_id,
                    label=(label or "").strip(),
                )
            )
            transition_index += 1
            continue
        note = re.match(rf"^note\s+(left|right)\s+of\s+({_ID})\s*:\s*(.*)$", text, re.IGNORECASE)
        if note:
            placement, target_id, label = note.groups()
            _state_node(model, target_id)
            model.metadata.setdefault("notes", []).append(
                {
                    "id": f"note-{note_index}",
                    "target": target_id,
                    "placement": placement.lower(),
                    "label": label,
                }
            )
            note_index += 1
            continue
        simple = re.match(rf"^({_ID})\s*:\s*(.*)$", text)
        if simple:
            state_id, label = simple.groups()
            _state_node(
                model,
                state_id,
                label=label,
                parent_id=parent_stack[-1] if parent_stack else None,
            )
            continue
        _unsupported(statement, diagnostics)
        raw.append(text)
    if parent_stack:
        raise MermaidParseError(f"Unclosed composite state: {parent_stack[-1]}")
    model.transitions.sort(key=lambda item: (item.source, item.target, item.label, item.id))
    for transition_index, transition in enumerate(model.transitions):
        transition.id = f"transition-{transition_index}"
    return _finish_document(
        source,
        model,
        diagnostics,
        raw,
        directives,
        accessibility,
        strict=strict,
    )


def serialize_mermaid(model: object) -> str:
    """Serialize one typed semantic model to canonical Mermaid syntax.

    Args:
        model: A :class:`FlowDiagram`, :class:`SequenceDiagram`,
            :class:`ClassDiagram`, :class:`EntityRelationshipDiagram`, or
            :class:`StateDiagram`.

    Returns:
        Deterministic Mermaid text suitable for parsing again or sending to the
        Official backend.

    Raises:
        TypeError: If ``model`` is not a supported semantic root.
    """

    serializers: list[tuple[type[object], Callable[[object], str]]] = [
        (FlowDiagram, lambda item: _serialize_flow(item)),
        (SequenceDiagram, lambda item: _serialize_sequence(item)),
        (ClassDiagram, lambda item: _serialize_class(item)),
        (EntityRelationshipDiagram, lambda item: _serialize_er(item)),
        (StateDiagram, lambda item: _serialize_state(item)),
    ]
    for model_type, serializer in serializers:
        if isinstance(model, model_type):
            return serializer(model)
    raise TypeError(f"Unsupported semantic model: {type(model).__name__}")


def _preamble(model: object) -> list[str]:
    metadata = model.metadata  # type: ignore[attr-defined]
    lines = [*metadata.get("directives", [])]
    if metadata.get("acc_title"):
        lines.append(f"accTitle: {metadata['acc_title']}")
    if metadata.get("acc_description"):
        lines.append(f"accDescr: {metadata['acc_description']}")
    return lines


def _serialize_flow(model: FlowDiagram) -> str:
    lines = [*_preamble(model), f"flowchart {model.direction}"]
    grouped: set[str] = set()

    def node_text(node: object) -> str:
        shape = {
            "rectangle": ("[", "]"),
            "rounded_rectangle": ("(", ")"),
            "diamond": ("{", "}"),
            "ellipse": ("((", "))"),
            "stadium": ("([", "])"),
            "subprocess": ("[[", "]]"),
            "hexagon": ("{{", "}}"),
            "cylinder": ("[(", ")]"),
            "parallelogram": ("[/", "/]"),
        }.get(node.shape.value, ("[", "]"))  # type: ignore[attr-defined]
        return (  # type: ignore[attr-defined]
            f"{node.id}{shape[0]}{_quote_label(node.label)}{shape[1]}"
        )

    def emit_group(group_id: str, indent: str = "    ") -> None:
        group = model.groups[group_id]
        lines.append(f"{indent}subgraph {group.id}[{_quote_label(group.label)}]")
        for child in model.groups.values():
            if child.parent_id == group.id:
                emit_group(child.id, indent + "    ")
        for node_id in group.node_ids:
            if node_id in model.nodes and node_id not in grouped:
                lines.append(f"{indent}    {node_text(model.nodes[node_id])}")
                grouped.add(node_id)
        lines.append(f"{indent}end")

    for group in model.groups.values():
        if group.parent_id is None:
            emit_group(group.id)
    for node in model.nodes.values():
        if node.id not in grouped:
            lines.append(f"    {node_text(node)}")
    for edge_index, edge in enumerate(model.edges):
        token = edge.metadata.get(
            "token",
            "-->" if edge.directed else "---",
        )
        label = f"|{edge.label}|" if edge.label else ""
        lines.append(f"    {edge.source} {token}{label} {edge.target}")
        token_style = {}
        if token == "-.->":
            token_style["dash"] = edge.style.dash
        elif token == "==>":
            token_style["line_width"] = edge.style.line_width
        extra_style = {
            key: value
            for key, value in edge.style.to_dict().items()
            if token_style.get(key) != value
        }
        if extra_style:
            lines.append(f"    linkStyle {edge_index} {_style_text(extra_style)}")
    class_defs: dict[str, dict[str, object]] = model.metadata.get("class_defs", {})
    for name, style in class_defs.items():
        lines.append(f"    classDef {name} {_style_text(style)}")
    for node in model.nodes.values():
        for class_name in sorted(node.classes):
            lines.append(f"    class {node.id} {class_name}")
        if node.style.to_dict() and not node.classes:
            lines.append(f"    style {node.id} {_style_text(node.style.to_dict())}")
    return "\n".join(lines) + "\n"


def _serialize_sequence(model: SequenceDiagram) -> str:
    lines = [*_preamble(model), "sequenceDiagram"]
    if model.autonumber:
        lines.append("    autonumber")
    for participant in model.participants.values():
        suffix = (
            f" as {_quote_label(participant.label)}" if participant.label != participant.id else ""
        )
        lines.append(f"    {participant.kind} {participant.id}{suffix}")
    for event in model.events:
        if event.kind == "message":
            arrow = event.metadata.get(
                "arrow",
                {
                    "solid": "->>",
                    "dashed": "-->>",
                    "async": "-)",
                    "lost": "-x",
                }.get(event.message_type, "->>"),
            )
            activation = event.metadata.get("activation") or ""
            lines.append(f"    {event.source}{arrow}{activation}{event.target}: {event.label}")
        elif event.kind == "note":
            participants = ",".join(event.participants)
            lines.append(f"    Note {event.placement} {participants}: {event.label}")
        elif event.kind in {"activate", "deactivate"}:
            lines.append(f"    {event.kind} {event.participants[0]}")
        elif event.kind == "fragment_start":
            lines.append(f"    {event.fragment_type} {event.label}".rstrip())
        elif event.kind == "fragment_else":
            separator = event.metadata.get("separator", "else")
            lines.append(f"    {separator} {event.label}".rstrip())
        elif event.kind == "fragment_end":
            lines.append("    end")
    return "\n".join(lines) + "\n"


def _serialize_class(model: ClassDiagram) -> str:
    lines = [*_preamble(model), "classDiagram", f"    direction {model.direction}"]
    namespaces: dict[str, list[ClassNode]] = {}
    unnamespaced: list[ClassNode] = []
    for node in model.classes.values():
        if node.namespace:
            namespaces.setdefault(node.namespace, []).append(node)
        else:
            unnamespaced.append(node)

    for namespace, nodes in namespaces.items():
        lines.append(f"    namespace {namespace} {{")
        for node in nodes:
            lines.extend(_serialize_class_node(node, indent="        "))
        lines.append("    }")
    for node in unnamespaced:
        lines.extend(_serialize_class_node(node, indent="    "))
    for relation in model.relationships:
        token = relation.metadata.get("token", "--")
        source_card = f' "{relation.source_cardinality}"' if relation.source_cardinality else ""
        target_card = f'"{relation.target_cardinality}" ' if relation.target_cardinality else ""
        label = f" : {relation.label}" if relation.label else ""
        lines.append(
            f"    {relation.source}{source_card} {token} {target_card}{relation.target}{label}"
        )
    for note in model.notes:
        target = f" for {note.participants[0]}" if note.participants else ""
        lines.append(f'    note{target} "{note.label}"')
    return "\n".join(lines) + "\n"


def _serialize_class_node(node: ClassNode, *, indent: str) -> list[str]:
    lines: list[str] = []
    label = f'["{node.label}"]' if node.label != node.id else ""
    lines.append(f"{indent}class {node.id}{label} {{")
    if node.stereotype:
        lines.append(f"{indent}    <<{node.stereotype}>>")
    lines.extend(f"{indent}    {item}" for item in node.attributes)
    lines.extend(f"{indent}    {item}" for item in node.methods)
    lines.append(f"{indent}}}")
    return lines


def _serialize_er(model: EntityRelationshipDiagram) -> str:
    lines = [*_preamble(model), "erDiagram", f"    direction {model.direction}"]
    for entity in model.entities.values():
        lines.append(f"    {entity.id} {{")
        for attribute in entity.attributes:
            keys = f" {','.join(attribute.keys)}" if attribute.keys else ""
            comment = f' "{attribute.comment}"' if attribute.comment else ""
            lines.append(f"        {attribute.type} {attribute.name}{keys}{comment}")
        lines.append("    }")
    for relation in model.relationships:
        label = _quote_label(relation.label)
        lines.append(
            f"    {relation.source} {relation.source_cardinality}--"
            f"{relation.target_cardinality} {relation.target} : {label}"
        )
    return "\n".join(lines) + "\n"


def _serialize_state(model: StateDiagram) -> str:
    lines = [*_preamble(model), "stateDiagram-v2", f"    direction {model.direction}"]
    children: dict[str | None, list[StateNode]] = {}
    for state in model.states.values():
        children.setdefault(state.parent_id, []).append(state)
    emitted_transitions: set[str] = set()

    def transition_line(transition: StateTransition, indent: str) -> str:
        source = (
            "[*]"
            if model.states.get(transition.source)
            and model.states[transition.source].kind == "start"
            else transition.source
        )
        target = (
            "[*]"
            if model.states.get(transition.target) and model.states[transition.target].kind == "end"
            else transition.target
        )
        label = f" : {transition.label}" if transition.label else ""
        return f"{indent}{source} --> {target}{label}"

    def emit_states(parent: str | None, indent: str) -> None:
        for state in children.get(parent, []):
            if state.kind in {"start", "end"}:
                continue
            stereotype = f" <<{state.kind}>>" if state.kind in {"choice", "fork", "join"} else ""
            if state.kind == "composite" or state.id in children:
                prefix = (
                    f'state "{state.label}" as {state.id}'
                    if state.label != state.id
                    else f"state {state.id}"
                )
                lines.append(f"{indent}{prefix} {{")
                emit_states(state.id, indent + "    ")
                for transition in model.transitions:
                    source = model.states.get(transition.source)
                    target = model.states.get(transition.target)
                    if (
                        source is not None
                        and target is not None
                        and source.parent_id == state.id
                        and target.parent_id == state.id
                    ):
                        lines.append(transition_line(transition, indent + "    "))
                        emitted_transitions.add(transition.id)
                lines.append(f"{indent}}}")
            else:
                prefix = (
                    f'state "{state.label}" as {state.id}'
                    if state.label != state.id
                    else f"state {state.id}"
                )
                lines.append(f"{indent}{prefix}{stereotype}")

    emit_states(None, "    ")
    for transition in model.transitions:
        if transition.id not in emitted_transitions:
            lines.append(transition_line(transition, "    "))
    for note in model.metadata.get("notes", []):
        lines.append(f"    note {note['placement']} of {note['target']}: {note['label']}")
    return "\n".join(lines) + "\n"


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _quote_label(value: str) -> str:
    if any(char in value for char in '[]{}():"'):
        return f'"{value.replace(chr(34), chr(92) + chr(34))}"'
    return value


def _style_text(style: object) -> str:
    mapping = (
        style.to_dict() if hasattr(style, "to_dict") else dict(style)  # type: ignore[arg-type]
    )
    key_map = {
        "fill": "fill",
        "line": "stroke",
        "text": "color",
        "line_width": "stroke-width",
        "dash": "stroke-dasharray",
    }
    return ",".join(
        f"{key_map.get(key, key.replace('_', '-'))}:{value}"
        for key, value in mapping.items()
        if value is not None
    )
