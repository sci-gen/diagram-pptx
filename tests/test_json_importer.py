from diagram_pptx import NodeShape
from diagram_pptx.importers import JsonImporter


def test_imports_dict_interchange_format() -> None:
    diagram = JsonImporter().parse(
        {
            "direction": "TB",
            "nodes": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B", "shape": "diamond"},
            ],
            "edges": [{"source": "a", "target": "b", "label": "next"}],
        }
    )
    assert diagram.direction == "TB"
    assert diagram.nodes["b"].shape is NodeShape.DIAMOND
    assert diagram.edges[0].label == "next"
