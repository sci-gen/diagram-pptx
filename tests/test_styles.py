import pytest

from diagram_pptx import (
    ColorMapStyle,
    DiagramTheme,
    ElementStyle,
    StyleResolver,
    contrast_text_color,
    sample_colormap,
)
from diagram_pptx.styles import normalize_color


def test_style_resolver_merge_precedence_and_color_map() -> None:
    theme = DiagramTheme(
        roles={"node.default": ElementStyle(fill="accent1", line="#111111")},
        classes={"brand": ElementStyle(fill="#123456")},
        ids={"db": ElementStyle(line="#222222")},
        color_map={"#123456": "#ABCDEF"},
    )
    resolved = StyleResolver(theme).resolve(
        element_id="db",
        role="node.default",
        classes={"brand"},
        source=ElementStyle(fill="#654321", line="#999999"),
        override=ElementStyle(text="#333333"),
    )

    assert resolved.fill == "#ABCDEF"
    assert resolved.line == "#222222"
    assert resolved.text == "#333333"


def test_preserve_and_replace_source_style_modes() -> None:
    theme = DiagramTheme(classes={"brand": ElementStyle(fill="#123456")})
    source = ElementStyle(fill="#654321")

    preserved = StyleResolver(theme, source_style="preserve").resolve(
        element_id="x", role="node.default", classes={"brand"}, source=source
    )
    replaced = StyleResolver(theme, source_style="replace").resolve(
        element_id="x", role="node.default", classes={"brand"}, source=source
    )

    assert preserved.fill == "#654321"
    assert replaced.fill == "#123456"


def test_mermaid_css_colors_are_normalized() -> None:
    assert normalize_color("#abcdef !important") == "#ABCDEF"
    assert normalize_color("hsl(240, 100%, 100%)") == "#FFFFFF"
    assert normalize_color("hsla(0, 100%, 50%, 0.5)") == "#FF000080"


def test_continuous_colormap_sampling_and_validation() -> None:
    assert sample_colormap("viridis", 0.0) == "#440154"
    assert sample_colormap("viridis", 1.0) == "#FDE725"
    assert sample_colormap("jet", 0.5).startswith("#")
    assert ColorMapStyle("plasma", text=0.2).color("text") == sample_colormap("plasma", 0.2)

    with pytest.raises(ValueError):
        sample_colormap("unknown", 0.5)
    with pytest.raises(ValueError):
        ColorMapStyle("jet", text=1.1)

    restored = ColorMapStyle.from_dict({"name": "viridis", "primary": 0.8, "secondary": 0.2})
    assert restored.to_dict() == {
        "name": "viridis",
        "primary": 0.8,
        "secondary": 0.2,
    }
    with pytest.raises(ValueError, match="require a name"):
        ColorMapStyle.from_dict({"primary": 0.8})
    with pytest.raises(ValueError, match="Unknown color-map"):
        ColorMapStyle.from_dict({"name": "jet", "unknown": 0.5})


def test_primary_secondary_shorthand_and_contrast_text() -> None:
    style = ColorMapStyle("viridis", primary=0.8, secondary=0.2)

    assert style.color("fill") == sample_colormap("viridis", 0.8)
    assert style.color("decision_fill") == sample_colormap("viridis", 0.2)
    assert style.color("line") == sample_colormap("viridis", 0.2)
    assert style.color("edge") == sample_colormap("viridis", 0.2)
    assert style.color("text") is None
    assert contrast_text_color("#101010") == "#FFFFFF"
    assert contrast_text_color("#F5F5F5") == "#111827"
