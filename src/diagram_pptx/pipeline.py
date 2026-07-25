"""Convenience pipelines composed from the public extension points."""

from __future__ import annotations

from typing import Any

from .importers.mermaid import MermaidFlowchartImporter
from .layout.layered import LayeredLayout
from .render.python_pptx import PythonPptxRenderer, RenderResult


def render_mermaid(
    source: str,
    *,
    slide: Any,
    bounds: tuple[float, float, float, float],
    importer: MermaidFlowchartImporter | None = None,
    layout_engine: LayeredLayout | None = None,
    renderer: PythonPptxRenderer | None = None,
) -> RenderResult:
    """Parse, lay out, and render a Mermaid flowchart onto ``slide``."""

    diagram = (importer or MermaidFlowchartImporter()).parse(source)
    layout = (layout_engine or LayeredLayout()).apply(diagram)
    return (renderer or PythonPptxRenderer()).render(layout, target=slide, bounds=bounds)
