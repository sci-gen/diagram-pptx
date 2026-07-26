import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from pptx import Presentation
from test_mermaid_frontend import SAMPLES, SOURCE_ONLY_SAMPLES

from diagram_pptx import compile_diagram, parse_mermaid
from diagram_pptx.importers import import_mermaid_svg
from diagram_pptx.official import mmdc_version
from diagram_pptx.render import PythonPptxRenderer
from diagram_pptx.scene import SceneConnector, SceneShape, SceneText


def test_mermaid_svg_importer_keeps_native_geometry_and_ignores_images() -> None:
    scene = import_mermaid_svg(
        """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
  <style>#test .messageLine0 { stroke: #333333; }</style>
  <script>alert(1)</script>
  <image href="https://example.com/a.png" width="10" height="10"/>
  <g id="flowchart-A-0" class="node">
    <rect x="10" y="10" width="60" height="30" fill="#abcdef"/>
    <text x="40" y="30">Alpha</text>
  </g>
  <path id="L-A-B-0" class="flowchart-link" d="M 70 25 L 130 25"
        fill="none" stroke="#123456"/>
  <g id="flowchart-B-1" class="node">
    <rect x="130" y="10" width="60" height="30"/>
  </g>
  <polygon id="custom-C" points="50,60 90,90 10,90" fill="#abcdef"/>
  <g id="flowchart-D-2" class="node" transform="translate(100,50)">
    <path class="label-container" d="M -10 -10 h 20 v 20 h -20 z"/>
  </g>
  <line data-id="i0" data-from="A" data-to="B"
        class="messageLine0" x1="20" y1="50" x2="180" y2="50"
        stroke="none" style="fill: none;"/>
</svg>
""",
        kind="flowchart",
    )

    assert any(isinstance(item, SceneShape) for item in scene.elements)
    assert any(isinstance(item, SceneConnector) for item in scene.elements)
    assert any(
        isinstance(item, SceneShape) and item.shape == "custom" and item.points
        for item in scene.elements
    )
    relative_path = next(
        item for item in scene.elements if isinstance(item, SceneShape) and item.semantic_id == "D"
    )
    assert relative_path.box.width == pytest.approx(20)
    assert relative_path.box.height == pytest.approx(20)
    assert all("image" not in item.role for item in scene.elements)
    message = next(
        item
        for item in scene.elements
        if isinstance(item, SceneConnector) and item.semantic_id == "event-0"
    )
    assert message.style.line == "#333333"
    assert (message.source_id, message.target_id) == ("A", "B")
    alpha_shapes = [
        item for item in scene.elements if isinstance(item, SceneShape) and item.semantic_id == "A"
    ]
    assert alpha_shapes[-1].text == "Alpha"
    assert not any(
        isinstance(item, SceneText) and item.semantic_id == "A" for item in scene.elements
    )

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = PythonPptxRenderer().render(
        scene,
        slide=slide,
        bounds=(1, 1, 8, 4),
    )
    assert result.group_shape is not None


def test_mermaid_svg_ignores_empty_label_rectangles() -> None:
    scene = import_mermaid_svg(
        """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">
  <g id="flowchart-A-0" class="node">
    <rect x="10" y="10" width="80" height="30"/>
    <g class="label"><rect/><text x="50" y="30">Alpha</text></g>
  </g>
</svg>
""",
        kind="flowchart",
    )

    shapes = [item for item in scene.elements if isinstance(item, SceneShape)]
    assert len(shapes) == 1
    assert shapes[0].text == "Alpha"


def test_sequence_self_message_is_enlarged_and_labels_are_offset() -> None:
    scene = import_mermaid_svg(
        """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 120">
  <text class="messageText" x="50" y="32">Prepare</text>
  <path data-id="i0" data-from="A" data-to="A" class="messageLine0"
        d="M 50 60 L 80 60 L 80 78 L 50 78"
        fill="none" stroke="#333333" marker-end="url(#arrow)"/>
  <text class="sequenceNumber" x="50" y="63">1</text>
</svg>
""",
        kind="sequence",
    )

    connector = next(item for item in scene.elements if isinstance(item, SceneConnector))
    label = next(
        item
        for item in scene.elements
        if isinstance(item, SceneText) and "messageText" in item.classes
    )
    number = next(
        item
        for item in scene.elements
        if isinstance(item, SceneText) and "sequenceNumber" in item.classes
    )

    assert connector.metadata["readable_self_message"] is True
    assert max(point.x for point in connector.points) - connector.points[0].x >= 80
    assert connector.points[-1].y - connector.points[0].y >= 30
    assert label.box.center.x > connector.points[0].x
    assert number.box.center.x < connector.points[0].x
    assert number.box.center.y < connector.points[0].y


def test_mermaid_svg_snaps_marker_margin_to_target_boundary() -> None:
    scene = import_mermaid_svg(
        """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60">
  <g id="flowchart-A-0" class="node">
    <rect x="10" y="15" width="50" height="30"/>
  </g>
  <path id="L_A_B_0" class="flowchart-link"
        d="M 60 30 L 126 30" fill="none" marker-end="url(#arrow)"/>
  <g id="flowchart-B-1" class="node">
    <rect x="130" y="15" width="50" height="30"/>
  </g>
</svg>
""",
        kind="flowchart",
    )

    connector = next(item for item in scene.elements if isinstance(item, SceneConnector))
    assert connector.points[-1].x == pytest.approx(120.0)
    assert connector.points[-1].y == pytest.approx(15.0)


def test_class_svg_recovers_solid_frames_source_arrow_and_label_background() -> None:
    scene = import_mermaid_svg(
        """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 80">
  <g id="classId-Repository-0" class="node">
    <rect x="10" y="10" width="70" height="60"
          fill="#ECECFF" stroke="#9370DB" stroke-dasharray="0 0"/>
  </g>
  <path id="id_Repository_SqlRepository_1"
        class="relation edge-pattern-dashed"
        d="M 90 40 L 150 40" fill="none" stroke="#333333"
        stroke-dasharray="3" marker-start="url(#extension)"/>
  <g class="edgeLabels">
    <g class="edgeLabel">
      <foreignObject x="95" y="28" width="50" height="24">
        <div xmlns="http://www.w3.org/1999/xhtml">implements</div>
      </foreignObject>
    </g>
  </g>
  <g id="classId-SqlRepository-1" class="node">
    <rect x="160" y="10" width="70" height="60"
          fill="#ECECFF" stroke="#9370DB" stroke-dasharray="0 0"/>
  </g>
</svg>
""",
        kind="class",
    )

    frames = [item for item in scene.elements if isinstance(item, SceneShape)]
    assert all(item.style.dash is None for item in frames)
    connector = next(item for item in scene.elements if isinstance(item, SceneConnector))
    assert connector.style.dash == "dash"
    assert connector.start_marker == "triangle"
    assert (connector.source_id, connector.target_id) == (
        "Repository",
        "SqlRepository",
    )
    assert connector.points[0].x == pytest.approx(70.0)
    assert connector.points[-1].x == pytest.approx(150.0)
    label = next(
        item for item in scene.elements if isinstance(item, SceneText) and item.text == "implements"
    )
    assert label.role == "edge.label"

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = PythonPptxRenderer().render(
        scene,
        slide=slide,
        bounds=(1, 1, 8, 4),
        group=False,
    )
    relation_parts = result.element_parts[connector.semantic_id]
    assert len(relation_parts) == 1
    assert 'type="triangle"' in relation_parts[0]._element.xml
    assert not any(shape.name.endswith(":marker-start") for shape in relation_parts)


@pytest.mark.official
@pytest.mark.parametrize("kind", list(SAMPLES))
def test_pinned_official_backend_compiles_all_families(
    kind: str,
    tmp_path: Path,
) -> None:
    executable = shutil.which("mmdc")
    if executable is None:
        pytest.skip("mmdc is not installed")
    assert (mmdc_version(executable) or "").startswith("11.16.")

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = compile_diagram(
        parse_mermaid(SAMPLES[kind]),
        slide=slide,
        bounds=(0.7, 0.7, 11.9, 6.1),
        backend="official",
        strict=True,
        timeout=60,
    )
    output = tmp_path / f"{kind}.pptx"
    presentation.save(output)

    assert result.backend_used == "official"
    assert result.mermaid_version.startswith("11.16.")
    assert result.scene is not None and result.scene.elements
    assert len(slide.shapes) == 1
    if kind == "sequence":
        assert len(result.nested_group_shapes) == 2
        actor_parts = [item for item in result.scene.elements if "actor-man" in item.classes]
        assert {item.metadata.get("composite_group") for item in actor_parts} == {
            "sequence-actor:actor-top:0",
            "sequence-actor:actor-bottom:0",
        }
        actor_lines = [item for item in actor_parts if isinstance(item, SceneConnector)]
        assert all(item.source_id is None and item.target_id is None for item in actor_lines)
    if kind == "state":
        assert len(result.nested_group_shapes) == 1
        assert result.nested_group_shapes[0].name == "diagram:state:pseudostate:root_end"
        end_parts = [
            item
            for item in result.scene.elements
            if isinstance(item, SceneShape) and item.semantic_id == "root_end"
        ]
        assert len(end_parts) == 4
        assert {item.metadata.get("composite_group") for item in end_parts} == {
            "state-pseudostate:root_end"
        }
    with ZipFile(output) as archive:
        xml = archive.read("ppt/slides/slide1.xml").decode()
    assert "<p:grpSp>" in xml
    if kind == "sequence":
        assert xml.count("<p:grpSp>") >= 3
    if kind == "state":
        assert xml.count("<p:grpSp>") >= 2
    assert "<a:blip" not in xml


@pytest.mark.official
@pytest.mark.parametrize("kind", list(SOURCE_ONLY_SAMPLES))
def test_pinned_official_backend_accepts_every_registered_source_family(
    kind: str,
) -> None:
    executable = shutil.which("mmdc")
    if executable is None:
        pytest.skip("mmdc is not installed")

    document = parse_mermaid(SOURCE_ONLY_SAMPLES[kind], strict=True)
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    result = compile_diagram(
        document,
        slide=slide,
        bounds=(0.7, 0.7, 11.9, 6.1),
        backend="official",
        strict=True,
        timeout=60,
    )

    assert result.backend_used == "official"
    assert result.scene.kind == kind
    assert result.scene.elements
    assert len(slide.shapes) == 1
