"""Extensible diagrams rendered as native PowerPoint shapes."""

from .layout.layered import LayeredLayout
from .model import (
    Diagram,
    DiagramEdge,
    DiagramError,
    DiagramGroup,
    DiagramLayout,
    DiagramNode,
    NodeShape,
    Point,
    PositionedGroup,
    PositionedNode,
    RoutedEdge,
)
from .pipeline import render_mermaid
from .render.python_pptx import PythonPptxRenderer, RenderResult, RenderTheme

__all__ = [
    "Diagram",
    "DiagramEdge",
    "DiagramError",
    "DiagramGroup",
    "DiagramLayout",
    "DiagramNode",
    "LayeredLayout",
    "NodeShape",
    "Point",
    "PositionedGroup",
    "PositionedNode",
    "PythonPptxRenderer",
    "RenderResult",
    "RenderTheme",
    "RoutedEdge",
    "render_mermaid",
]

__version__ = "0.1.0"
