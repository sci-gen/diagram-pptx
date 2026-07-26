from diagram_pptx import NodeShape
from diagram_pptx.importers import MermaidFlowchartImporter, MermaidParseError

SOURCE = """
flowchart LR
    A[Receive request] --> B{Valid?}
    B -->|Yes| C(Process)
    B -.->|No| D((Reject))
    subgraph Ops[Operations]
        C --> E[[Record result]]
    end
    classDef success fill:#E5F6EA,stroke:#238636,color:#14532D,stroke-width:2px
    class C,E success
    style D fill:#FDECEC,stroke:#C53B3B
"""


def test_parses_flowchart_semantics() -> None:
    diagram = MermaidFlowchartImporter().parse(SOURCE)

    assert diagram.direction == "LR"
    assert list(diagram.nodes) == ["A", "B", "C", "D", "E"]
    nodes = diagram.node_map()
    assert nodes["A"].shape is NodeShape.RECTANGLE
    assert nodes["B"].shape is NodeShape.DIAMOND
    assert nodes["C"].shape is NodeShape.ROUNDED_RECTANGLE
    assert nodes["D"].shape is NodeShape.ELLIPSE
    assert nodes["E"].shape is NodeShape.SUBPROCESS
    assert nodes["C"].style["fill"] == "#E5F6EA"
    assert nodes["C"].style["line_width"] == 2.0
    assert nodes["D"].style["line"] == "#C53B3B"

    assert len(diagram.edges) == 4
    assert diagram.edges[1].label == "Yes"
    assert diagram.edges[2].label == "No"
    assert diagram.edges[2].style["dash"] == "dash"
    assert diagram.groups["Ops"].node_ids == ["C", "E"]


def test_supports_chained_edges_and_semicolons() -> None:
    diagram = MermaidFlowchartImporter().parse("flowchart TB; A[One] --> B[Two] --> C[Three]")
    assert [(edge.source, edge.target) for edge in diagram.edges] == [
        ("A", "B"),
        ("B", "C"),
    ]


def test_supports_text_between_edge_dashes() -> None:
    diagram = MermaidFlowchartImporter().parse("flowchart LR\nA[One] -- accepted --> B[Two]")
    assert diagram.edges[0].label == "accepted"


def test_rejects_non_flowchart_diagrams() -> None:
    try:
        MermaidFlowchartImporter().parse("sequenceDiagram\nA->>B: Hello")
    except MermaidParseError as exc:
        assert "only Mermaid flowcharts" in str(exc)
    else:
        raise AssertionError("Expected MermaidParseError")
