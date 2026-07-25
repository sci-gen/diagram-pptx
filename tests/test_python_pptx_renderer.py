from pathlib import Path
from zipfile import ZipFile

from pptx import Presentation
from pptx.util import Inches

from diagram_pptx import render_mermaid


def test_renders_only_native_shapes(tmp_path: Path) -> None:
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = render_mermaid(
        """
        flowchart LR
            A[Receive] --> B{Valid?}
            B -->|Yes| C[Process]
            B -.->|No| D[Reject]
        """,
        slide=slide,
        bounds=(0.7, 0.7, 11.9, 6.1),
    )
    output = tmp_path / "native.pptx"
    presentation.save(output)

    assert set(result.node_shapes) == {"A", "B", "C", "D"}
    assert len(result.connectors) >= 3
    assert len(result.edge_label_shapes) == 2
    assert all(shape.name.startswith("diagram-node:") for shape in result.node_shapes.values())

    reopened = Presentation(output)
    assert len(reopened.slides[0].shapes) == len(result.shapes)
    with ZipFile(output) as archive:
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "<p:cxnSp>" in slide_xml
    assert "tailEnd" in slide_xml
    assert "<a:blip" not in slide_xml
