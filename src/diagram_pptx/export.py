"""Matplotlib-like SVG, PNG, and JPEG export for diagram objects."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from .compiler import (
    BackendName,
    ColorMapName,
    ColorMapOptions,
    CompileBackend,
    SceneResult,
    StylePreset,
    build_scene,
)
from .diagnostics import Diagnostic, ImageExportDependencyError
from .model import MermaidDocument, SemanticDiagram
from .render.svg import SvgRenderer
from .styles import ColorMapStyle, DiagramTheme, ElementStyle, SourceStylePolicy, normalize_color

ImageFormat = Literal["svg", "png", "jpeg", "jpg"]


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Metadata for a diagram written to disk."""

    path: Path
    format: str
    width_px: int
    height_px: int
    backend_used: str
    mermaid_version: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe result suitable for an LLM tool response."""

        return {
            "path": str(self.path),
            "format": self.format,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "backend_used": self.backend_used,
            "mermaid_version": self.mermaid_version,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


def save_diagram(
    diagram: MermaidDocument | SemanticDiagram,
    path: str | Path,
    *,
    format: ImageFormat | None = None,
    dpi: float = 96.0,
    width_px: int | None = None,
    height_px: int | None = None,
    background: str | None = None,
    label_background: str | None = "#FFFFFF",
    quality: int = 95,
    max_pixels: int = 100_000_000,
    backend: CompileBackend | BackendName = "native",
    style: StylePreset = "native",
    theme: DiagramTheme | Mapping[str, Any] | None = None,
    colors: ColorMapStyle | ColorMapOptions | ColorMapName | None = None,
    source_style: SourceStylePolicy = "merge",
    style_overrides: Mapping[str, ElementStyle | Mapping[str, Any]] | None = None,
    mmdc_path: str | None = None,
    strict: bool = False,
    timeout: float = 30.0,
) -> ExportResult:
    """Save a diagram as SVG, PNG, or JPEG.

    The file format is inferred from ``path`` unless ``format`` is provided.
    SVG remains vector output, so ``dpi`` only affects PNG and JPEG. Explicit
    ``width_px`` or ``height_px`` override DPI-derived raster dimensions while
    preserving the aspect ratio when only one dimension is supplied.
    ``label_background`` controls the fill behind connector and message labels;
    pass the same value as ``background`` to make labels blend into the canvas.
    """

    target = Path(path)
    output_format = _normalize_format(format or target.suffix.lstrip("."))
    scene_result = build_scene(
        diagram,
        backend=backend,
        style=style,
        theme=theme,
        colors=colors,
        label_background=label_background,
        source_style=source_style,
        style_overrides=style_overrides,
        mmdc_path=mmdc_path,
        strict=strict,
        timeout=timeout,
    )
    if output_format == "svg":
        rendered = SvgRenderer().render(
            scene_result.scene,
            width_px=width_px,
            height_px=height_px,
            background=background,
        )
        target.write_text(rendered.svg, encoding="utf-8")
        resolved_width, resolved_height = rendered.width_px, rendered.height_px
    else:
        raster = _raster_bytes(
            scene_result,
            output_format=output_format,
            dpi=dpi,
            width_px=width_px,
            height_px=height_px,
            background=background,
            quality=quality,
            max_pixels=max_pixels,
        )
        target.write_bytes(raster.data)
        resolved_width, resolved_height = raster.width_px, raster.height_px
    return ExportResult(
        path=target.resolve(),
        format=output_format,
        width_px=resolved_width,
        height_px=resolved_height,
        backend_used=scene_result.backend_used,
        mermaid_version=scene_result.mermaid_version,
        diagnostics=scene_result.diagnostics,
    )


def to_svg(
    diagram: MermaidDocument | SemanticDiagram,
    *,
    width_px: int | None = None,
    height_px: int | None = None,
    background: str | None = None,
    label_background: str | None = "#FFFFFF",
    **compile_options: Any,
) -> str:
    """Return a self-contained SVG string without writing a file."""

    result = build_scene(diagram, label_background=label_background, **compile_options)
    return (
        SvgRenderer()
        .render(
            result.scene,
            width_px=width_px,
            height_px=height_px,
            background=background,
        )
        .svg
    )


def to_png(
    diagram: MermaidDocument | SemanticDiagram,
    *,
    dpi: float = 96.0,
    width_px: int | None = None,
    height_px: int | None = None,
    background: str | None = None,
    label_background: str | None = "#FFFFFF",
    max_pixels: int = 100_000_000,
    **compile_options: Any,
) -> bytes:
    """Return PNG bytes; install ``diagram-pptx[image]`` first."""

    result = build_scene(diagram, label_background=label_background, **compile_options)
    return _raster_bytes(
        result,
        output_format="png",
        dpi=dpi,
        width_px=width_px,
        height_px=height_px,
        background=background,
        quality=95,
        max_pixels=max_pixels,
    ).data


def to_jpeg(
    diagram: MermaidDocument | SemanticDiagram,
    *,
    dpi: float = 96.0,
    width_px: int | None = None,
    height_px: int | None = None,
    background: str = "#FFFFFF",
    label_background: str | None = "#FFFFFF",
    quality: int = 95,
    max_pixels: int = 100_000_000,
    **compile_options: Any,
) -> bytes:
    """Return JPEG bytes with transparency flattened onto ``background``."""

    result = build_scene(diagram, label_background=label_background, **compile_options)
    return _raster_bytes(
        result,
        output_format="jpeg",
        dpi=dpi,
        width_px=width_px,
        height_px=height_px,
        background=background,
        quality=quality,
        max_pixels=max_pixels,
    ).data


@dataclass(frozen=True, slots=True)
class _RasterResult:
    data: bytes
    width_px: int
    height_px: int


def _raster_bytes(
    result: SceneResult,
    *,
    output_format: Literal["png", "jpeg"],
    dpi: float,
    width_px: int | None,
    height_px: int | None,
    background: str | None,
    quality: int,
    max_pixels: int,
) -> _RasterResult:
    if dpi <= 0:
        raise ValueError("dpi must be greater than zero")
    if max_pixels <= 0:
        raise ValueError("max_pixels must be greater than zero")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100")
    try:
        import resvg_py
    except ImportError as exc:
        raise ImageExportDependencyError(
            "PNG and JPEG export require optional image dependencies. Install them with "
            '`pip install "diagram-pptx[image]"` or install all optional runtime '
            'features with `pip install "diagram-pptx[all]"`.'
        ) from exc

    natural = SvgRenderer().render(result.scene, background=background)
    resolved_width, resolved_height = _raster_dimensions(
        natural.width_px,
        natural.height_px,
        dpi=dpi,
        width_px=width_px,
        height_px=height_px,
    )
    if resolved_width * resolved_height > max_pixels:
        raise ValueError(
            f"Raster output would contain {resolved_width * resolved_height:,} pixels; "
            f"the configured maximum is {max_pixels:,}. Reduce dpi or pixel dimensions."
        )
    rendered = SvgRenderer().render(
        result.scene,
        width_px=resolved_width,
        height_px=resolved_height,
        background=background,
    )
    png = resvg_py.svg_to_bytes(
        svg_string=rendered.svg,
        width=resolved_width,
        height=resolved_height,
        dpi=dpi,
        sans_serif_family=_default_sans_serif_family(),
    )
    if output_format == "png":
        return _RasterResult(bytes(png), resolved_width, resolved_height)
    return _RasterResult(
        _png_to_jpeg(bytes(png), background=background or "#FFFFFF", quality=quality, dpi=dpi),
        resolved_width,
        resolved_height,
    )


def _png_to_jpeg(png: bytes, *, background: str, quality: int, dpi: float) -> bytes:
    try:
        from PIL import Image, ImageColor
    except ImportError as exc:
        raise ImageExportDependencyError(
            'JPEG export requires Pillow. Install it with `pip install "diagram-pptx[image]"`.'
        ) from exc
    normalized = normalize_color(background)
    if normalized in {"none", "transparent", "#00000000"}:
        raise ValueError("JPEG does not support transparency; provide an opaque background color")
    if len(normalized) == 9:
        normalized = normalized[:7]
    try:
        background_rgb = ImageColor.getrgb(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid JPEG background color: {background!r}") from exc
    with Image.open(BytesIO(png)) as source:
        rgba = source.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, background_rgb)
        flattened.paste(rgba, mask=rgba.getchannel("A"))
        output = BytesIO()
        flattened.save(
            output,
            format="JPEG",
            quality=quality,
            dpi=(dpi, dpi),
            optimize=True,
        )
        return output.getvalue()


def _raster_dimensions(
    natural_width: int,
    natural_height: int,
    *,
    dpi: float,
    width_px: int | None,
    height_px: int | None,
) -> tuple[int, int]:
    if width_px is not None and width_px <= 0:
        raise ValueError("width_px must be greater than zero")
    if height_px is not None and height_px <= 0:
        raise ValueError("height_px must be greater than zero")
    if width_px is not None and height_px is not None:
        return width_px, height_px
    if width_px is not None:
        return width_px, max(1, round(natural_height * width_px / natural_width))
    if height_px is not None:
        return max(1, round(natural_width * height_px / natural_height)), height_px
    scale = dpi / 96.0
    return max(1, round(natural_width * scale)), max(1, round(natural_height * scale))


def _normalize_format(value: str) -> Literal["svg", "png", "jpeg"]:
    normalized = value.strip().lower()
    if normalized == "jpg":
        return "jpeg"
    if normalized not in {"svg", "png", "jpeg"}:
        raise ValueError(
            f"Cannot infer a supported image format from {value!r}; use svg, png, jpg, or jpeg"
        )
    return normalized


def _default_sans_serif_family() -> str:
    if sys.platform == "darwin":
        return "Helvetica"
    if sys.platform.startswith("win"):
        return "Arial"
    return "DejaVu Sans"
