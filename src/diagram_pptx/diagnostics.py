"""Structured diagnostics shared by parsers, backends, and compilers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

DiagnosticSeverity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Structured non-fatal parser or backend message with source location."""

    code: str
    message: str
    severity: DiagnosticSeverity = "warning"
    line: int | None = None
    column: int | None = None
    statement: str | None = None
    backend: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "message": self.message,
                "severity": self.severity,
                "line": self.line,
                "column": self.column,
                "statement": self.statement,
                "backend": self.backend,
            }.items()
            if value is not None
        }


class DiagramPptxError(RuntimeError):
    """Base exception for compilation failures."""


class MermaidParseError(DiagramPptxError, ValueError):
    """Raised when Mermaid input cannot be parsed under the requested policy."""


class PartialModelMutationError(DiagramPptxError):
    """Raised when a partial semantic model was changed before compilation."""


class MermaidRuntimeError(DiagramPptxError):
    """Raised when the official Mermaid runtime cannot produce usable SVG."""


class ImageExportDependencyError(DiagramPptxError, ImportError):
    """Raised when an optional image-export runtime is not installed."""
