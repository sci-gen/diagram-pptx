from __future__ import annotations

import shutil
from io import BytesIO
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from diagram_pptx import (
    ExportResult,
    parse_mermaid,
    save_diagram,
    to_jpeg,
    to_png,
)

SOURCE = """\
flowchart LR
    A[Start] -->|valid| B{Check}
    B --> C[(Database)]
"""

FAMILY_SOURCES = [
    SOURCE,
    """\
sequenceDiagram
    participant A as API
    participant W as Worker
    A->>W: Run
    W-->>A: Done
""",
    """\
classDiagram
    class Order {
      +submit()
    }
    class Repository
    Order --> Repository : stores
""",
    """\
erDiagram
    CUSTOMER ||--o{ ORDER : places
    CUSTOMER {
      string email PK
    }
    ORDER {
      int id PK
    }
""",
    """\
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start
    Running --> [*] : complete
""",
]


def test_document_exports_self_contained_svg(tmp_path) -> None:
    document = parse_mermaid(SOURCE)
    document.model.nodes["A"].label = "Edited"

    result = document.save(tmp_path / "diagram.svg", style="official")

    assert isinstance(result, ExportResult)
    assert result.format == "svg"
    assert result.backend_used == "native"
    svg = result.path.read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.get("viewBox")
    assert "Edited" in svg
    assert 'data-semantic-id="A"' in svg
    assert "<script" not in svg
    assert "http://www.w3.org/1999/xlink" not in svg


def test_typed_model_has_svg_convenience_method() -> None:
    document = parse_mermaid(SOURCE)

    svg = document.model.to_svg(colors={"name": "viridis", "primary": 0.8})

    assert svg.startswith("<?xml")
    assert "#7ECF56" in svg


@pytest.mark.parametrize("source", FAMILY_SOURCES)
def test_all_native_families_export_svg(source) -> None:
    svg = parse_mermaid(source).to_svg()

    assert "<svg" in svg
    assert "data-semantic-id=" in svg


def test_png_dpi_scales_natural_dimensions(tmp_path) -> None:
    document = parse_mermaid(SOURCE)
    svg_result = save_diagram(document, tmp_path / "base.svg")

    png_result = document.save(tmp_path / "high-resolution.png", dpi=192)

    assert png_result.format == "png"
    assert png_result.width_px == svg_result.width_px * 2
    assert png_result.height_px == svg_result.height_px * 2
    with Image.open(png_result.path) as image:
        assert image.format == "PNG"
        assert image.size == (png_result.width_px, png_result.height_px)


def test_png_explicit_width_preserves_aspect_ratio() -> None:
    document = parse_mermaid(SOURCE)

    data = to_png(document, width_px=1200, background="transparent")

    with Image.open(BytesIO(data)) as image:
        assert image.format == "PNG"
        assert image.width == 1200
        assert image.height > 0


def test_svg_label_background_matches_a_non_white_canvas() -> None:
    color = "#243447"
    default_svg = parse_mermaid(SOURCE).to_svg()
    default_root = ET.fromstring(default_svg)
    default_label_group = next(
        element for element in default_root.iter() if element.get("data-role") == "edge.default"
    )
    default_label_box = next(
        element for element in default_label_group if element.tag.endswith("rect")
    )
    svg = parse_mermaid(SOURCE).to_svg(
        background=color,
        label_background=color,
    )
    root = ET.fromstring(svg)
    label_group = next(
        element for element in root.iter() if element.get("data-role") == "edge.default"
    )
    label_box = next(element for element in label_group if element.tag.endswith("rect"))

    assert default_label_box.get("fill") == "#FFFFFF"
    assert label_box.get("fill") == color


@pytest.mark.parametrize("suffix", ["jpg", "jpeg"])
def test_jpeg_aliases_flatten_transparency(tmp_path, suffix) -> None:
    document = parse_mermaid(SOURCE)
    path = tmp_path / f"diagram.{suffix}"

    result = document.save(path, dpi=144, background="#F4F1EA", quality=88)

    assert result.format == "jpeg"
    with Image.open(path) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (result.width_px, result.height_px)


def test_to_jpeg_rejects_transparent_background() -> None:
    document = parse_mermaid(SOURCE)

    with pytest.raises(ValueError, match="does not support transparency"):
        to_jpeg(document, background="transparent")


def test_raster_export_guards_maximum_pixels() -> None:
    document = parse_mermaid(SOURCE)

    with pytest.raises(ValueError, match="configured maximum"):
        to_png(document, width_px=10_000, height_px=10_000, max_pixels=1_000_000)


def test_unknown_save_suffix_is_explicit(tmp_path) -> None:
    document = parse_mermaid(SOURCE)

    with pytest.raises(ValueError, match="svg, png, jpg, or jpeg"):
        document.save(tmp_path / "diagram.bmp")


def test_auto_backend_records_native_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("diagram_pptx.official.find_mmdc", lambda _: None)
    document = parse_mermaid(SOURCE)

    result = save_diagram(document, tmp_path / "fallback.svg", backend="auto")

    assert result.backend_used == "native"
    assert any(item.code == "mmdc-not-found-native-fallback" for item in result.diagnostics)


@pytest.mark.official
def test_official_geometry_exports_through_same_svg_renderer() -> None:
    if shutil.which("mmdc") is None:
        pytest.skip("mmdc is not installed")

    svg = parse_mermaid(SOURCE).to_svg(backend="official")

    assert "<svg" in svg
    assert "data-semantic-id=" in svg
