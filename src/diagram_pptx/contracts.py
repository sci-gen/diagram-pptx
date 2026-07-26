"""Structural protocols for replaceable frontends, layouts, and renderers."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from .model import SemanticDiagram
from .scene import DrawingScene

SourceT = TypeVar("SourceT", contravariant=True)
TargetT = TypeVar("TargetT", contravariant=True)
ResultT = TypeVar("ResultT", covariant=True)


class DiagramFrontend(Protocol[SourceT]):
    def parse(self, source: SourceT) -> SemanticDiagram: ...


class LayoutBackend(Protocol):
    def apply(self, diagram: SemanticDiagram) -> DrawingScene: ...


class DiagramRenderer(Protocol[TargetT, ResultT]):
    def render(
        self,
        scene: DrawingScene,
        *,
        target: TargetT,
        bounds: tuple[float, float, float, float],
        **options: Any,
    ) -> ResultT: ...


# Temporary import aliases for pre-alpha adapter code.
DiagramImporter = DiagramFrontend
LayoutEngine = LayoutBackend
