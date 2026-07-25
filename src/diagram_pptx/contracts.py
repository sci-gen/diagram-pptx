"""Small protocols that keep import, layout, and rendering replaceable."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from .model import Diagram, DiagramLayout

SourceT = TypeVar("SourceT", contravariant=True)
TargetT = TypeVar("TargetT", contravariant=True)
ResultT = TypeVar("ResultT", covariant=True)


class DiagramImporter(Protocol[SourceT]):
    def parse(self, source: SourceT) -> Diagram: ...


class LayoutEngine(Protocol):
    def apply(self, diagram: Diagram) -> DiagramLayout: ...


class DiagramRenderer(Protocol[TargetT, ResultT]):
    def render(
        self,
        layout: DiagramLayout,
        *,
        target: TargetT,
        bounds: tuple[float, float, float, float],
        **options: Any,
    ) -> ResultT: ...
