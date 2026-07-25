import pytest

from diagram_pptx.importers import MermaidFlowchartImporter
from diagram_pptx.layout import LayeredLayout


@pytest.mark.parametrize("direction", ["LR", "RL", "TB", "BT"])
def test_layout_positions_every_node_and_routes_edges(direction: str) -> None:
    diagram = MermaidFlowchartImporter().parse(
        f"flowchart {direction}\nA[Start] --> B{{Choose}}\nB --> C[Done]\nB --> D[Retry]"
    )
    layout = LayeredLayout().apply(diagram)

    assert len(layout.nodes) == 4
    assert len(layout.edges) == 3
    assert layout.width > 0
    assert layout.height > 0
    assert all(len(edge.points) >= 2 for edge in layout.edges)
    assert all(node.width > 0 and node.height > 0 for node in layout.nodes)


def test_cycles_are_spread_across_ranks() -> None:
    diagram = MermaidFlowchartImporter().parse("flowchart LR\nA --> B\nB --> C\nC --> A\nC --> D")
    layout = LayeredLayout().apply(diagram)
    ranks = {node.node.id: node.rank for node in layout.nodes}
    assert len({ranks["A"], ranks["B"], ranks["C"]}) == 3
    assert ranks["D"] > max(ranks["A"], ranks["B"], ranks["C"])


def test_self_loop_routes_outside_the_node() -> None:
    diagram = MermaidFlowchartImporter().parse("flowchart LR\nA[Retry] --> A")
    layout = LayeredLayout().apply(diagram)
    node = layout.nodes[0]
    points = layout.edges[0].points
    assert min(point.y for point in points) < node.y
    assert max(point.x for point in points) > node.x + node.width


def test_group_encloses_members() -> None:
    diagram = MermaidFlowchartImporter().parse(
        "flowchart LR\nsubgraph G[Group]\nA --> B\nend\nB --> C"
    )
    layout = LayeredLayout().apply(diagram)
    group = layout.groups[0]
    members = [node for node in layout.nodes if node.node.id in {"A", "B"}]
    assert all(group.x <= node.x and group.y <= node.y for node in members)
    assert all(
        group.x + group.width >= node.x + node.width
        and group.y + group.height >= node.y + node.height
        for node in members
    )
