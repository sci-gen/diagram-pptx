import json

import pytest

from diagram_pptx import (
    ClassDiagram,
    EntityRelationshipDiagram,
    FlowDiagram,
    MermaidParseError,
    SequenceDiagram,
    StateDiagram,
    diagram_from_dict,
    parse_mermaid,
    serialize_mermaid,
)

SAMPLES = {
    "flowchart": """\
flowchart LR
subgraph Core[Core services]
    api([API]) --> db[(Database)]
end
db -->|retry| db
classDef storage fill:#E5F6EA,stroke:#238636
class db storage
linkStyle 0 stroke:#123456
""",
    "sequence": """\
sequenceDiagram
autonumber
actor User as Customer
participant API
User->>API: Request
activate API
Note right of API: Validate
alt accepted
API-->>User: Response
else rejected
API-xUser: Error
end
deactivate API
""",
    "class": """\
classDiagram
direction LR
class Repository {
    <<interface>>
    +find(id)
}
class SqlRepository {
    -connection
    +find(id)
}
Repository <|.. SqlRepository : implements
note for SqlRepository "Native implementation"
""",
    "er": """\
erDiagram
direction LR
CUSTOMER {
    string id PK
    string email UK "login address"
}
ORDER {
    int id PK
    string customer_id FK
}
CUSTOMER ||--o{ ORDER : places
""",
    "state": """\
stateDiagram-v2
direction LR
[*] --> Idle
state "Running workflow" as Running {
    [*] --> Work
    Work --> [*]
}
Idle --> Running : start
Running --> [*]
note right of Idle: waiting
""",
}


@pytest.mark.parametrize(
    ("kind", "model_type"),
    [
        ("flowchart", FlowDiagram),
        ("sequence", SequenceDiagram),
        ("class", ClassDiagram),
        ("er", EntityRelationshipDiagram),
        ("state", StateDiagram),
    ],
)
def test_typed_parse_json_and_mermaid_round_trips(kind: str, model_type: type) -> None:
    document = parse_mermaid(SAMPLES[kind])

    assert isinstance(document.model, model_type)
    assert document.is_fully_modeled
    assert diagram_from_dict(json.loads(json.dumps(document.model.to_dict()))) == document.model

    reparsed = parse_mermaid(serialize_mermaid(document.model))
    assert reparsed.model == document.model


def test_orm_style_mutation_and_selection() -> None:
    document = parse_mermaid(SAMPLES["flowchart"])
    document.model.nodes["db"].label = "Primary DB"

    assert document.model_changed
    assert document.model.nodes["db"].label == "Primary DB"
    assert document.model.select(class_="storage") == [document.model.nodes["db"]]


def test_unsupported_syntax_is_diagnostic_or_strict_error() -> None:
    source = "flowchart LR\nA --> B\nclick A https://example.com"
    document = parse_mermaid(source)

    assert not document.is_fully_modeled
    assert document.raw_statements == ["click A https://example.com"]
    assert document.diagnostics[0].line == 3

    with pytest.raises(MermaidParseError, match="Unsupported Mermaid syntax"):
        parse_mermaid(source, strict=True)


def test_state_pseudostates_have_no_visible_internal_id() -> None:
    document = parse_mermaid("stateDiagram-v2\n[*] --> Ready\nReady --> [*]")
    pseudostates = [
        state for state in document.model.states.values() if state.kind in {"start", "end"}
    ]

    assert pseudostates
    assert all(state.label == "" for state in pseudostates)
