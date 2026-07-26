import json

import pytest

from diagram_pptx import (
    MERMAID_SYNTAX_FAMILIES,
    ClassDiagram,
    EntityRelationshipDiagram,
    FlowDiagram,
    MermaidParseError,
    MermaidSourceDiagram,
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


SOURCE_ONLY_SAMPLES = {
    "swimlanes": "swimlane-beta LR\nsubgraph Team\nA[Work]\nend",
    "journey": "journey\ntitle Day\nsection Work\nTask: 5: User",
    "gantt": "gantt\ntitle Plan\ndateFormat YYYY-MM-DD\nTask: 2026-01-01, 1d",
    "pie": 'pie title Pets\n"Dogs" : 60\n"Cats" : 40',
    "quadrant": "quadrantChart\nx-axis Low --> High\nA: [0.3, 0.5]\nB: [0.7, 0.8]",
    "requirement": """\
requirementDiagram
requirement test_req {
  id: 1
  text: "Test requirement"
  risk: low
  verifymethod: test
}""",
    "gitgraph": "gitGraph\ncommit\nbranch develop\ncheckout develop\ncommit",
    "c4": (
        'C4Context\nPerson(user, "User")\nSystem(system, "System")\n'
        'Rel(user, system, "Uses")'
    ),
    "mindmap": "mindmap\n  root((mindmap))\n    Topic",
    "timeline": "timeline\ntitle History\n2026 : Event",
    "zenuml": "zenuml\nAlice->Bob: Hello",
    "sankey": "sankey-beta\nA,B,10",
    "xychart": 'xychart-beta\nx-axis "x" [1, 2]\ny-axis "y" 0 --> 2\nline [1, 2]',
    "block": "block-beta\ncolumns 2\nA B",
    "packet": 'packet\n0-7: "Header"\n8-15: "Payload"',
    "kanban": "kanban\ncolumn1[Todo]\ntask1[Task]",
    "architecture": "architecture-beta\nservice api(server)[API]",
    "radar": (
        'radar-beta\naxis a["Speed"], b["Quality"]\n'
        'curve c["Product"]{1, 2}\nmax 5\nmin 0'
    ),
    "eventmodeling": "eventmodeling\ntf 01 ui CartUI\ntf 02 cmd AddItem",
    "treemap": 'treemap-beta\n"Root"\n  "Leaf": 10',
    "venn": "venn-beta\nset A\nset B\nunion A,B",
    "ishikawa": "ishikawa-beta\nProblem\n  Cause",
    "wardley": "wardley-beta\nanchor User [0.9, 0.5]\ncomponent Need [0.8, 0.5]",
    "cynefin": 'cynefin-beta\nclear\n  "Known practice"\ncomplex\n  "Explore"',
    "treeview": "treeView-beta\nRoot\n  Child",
    "railroad": 'railroad-ebnf-beta\nroot = "a" ;',
}


def test_registry_covers_every_documented_family_and_experimental_railroad() -> None:
    assert len(MERMAID_SYNTAX_FAMILIES) == 31
    assert {item.kind for item in MERMAID_SYNTAX_FAMILIES} == {
        *SAMPLES,
        *SOURCE_ONLY_SAMPLES,
    }


@pytest.mark.parametrize("kind", SOURCE_ONLY_SAMPLES)
def test_official_only_families_are_lossless_and_strict_parse_accepts_them(kind: str) -> None:
    source = SOURCE_ONLY_SAMPLES[kind]
    document = parse_mermaid(source, strict=True)

    assert isinstance(document.model, MermaidSourceDiagram)
    assert document.model.kind == kind
    assert serialize_mermaid(document.model) == source
    assert document.required_backend == "official"
    assert document.modeling_rate == 0.0
    assert not document.is_fully_modeled
    assert diagram_from_dict(document.model.to_dict()) == document.model


def test_frontmatter_is_accepted_and_preserved_for_typed_and_source_models() -> None:
    flow_source = """\
---
config:
  look: handDrawn
---
flowchart LR
A --> B
"""
    flow = parse_mermaid(flow_source)
    serialized = serialize_mermaid(flow.model)
    assert serialized.startswith("---\nconfig:\n  look: handDrawn\n---\nflowchart LR")

    pie_source = """\
---
config:
  theme: forest
---
pie
"A": 1
"""
    pie = parse_mermaid(pie_source, strict=True)
    assert serialize_mermaid(pie.model) == pie_source
