"""Mermaid 11.16 syntax-family registry.

The registry mirrors Mermaid's public syntax documentation and detector
headers.  It deliberately contains only independently maintained identifiers
and header patterns; Mermaid parser or renderer code is not copied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MERMAID_COMPATIBILITY_VERSION = "11.16.0"


@dataclass(frozen=True, slots=True)
class MermaidSyntaxFamily:
    """One Mermaid syntax family and the first-line declaration it accepts."""

    kind: str
    title: str
    header_pattern: str
    documentation: str
    typed_model: bool = False
    native_backend: bool = False
    experimental: bool = False

    def matches(self, header: str) -> bool:
        return re.match(self.header_pattern, header) is not None


_DOCS = "https://mermaid.js.org/syntax/"

MERMAID_SYNTAX_FAMILIES: tuple[MermaidSyntaxFamily, ...] = (
    MermaidSyntaxFamily(
        "flowchart",
        "Flowchart",
        r"^\s*(?:flowchart|graph)\s+(?:TB|TD|BT|RL|LR)\b",
        f"{_DOCS}flowchart.html",
        typed_model=True,
        native_backend=True,
    ),
    MermaidSyntaxFamily(
        "swimlanes",
        "Swimlanes",
        r"^\s*swimlane-beta(?:\s+(?:TB|TD|BT|RL|LR))?\s*$",
        f"{_DOCS}swimlanes.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "sequence",
        "Sequence Diagram",
        r"^\s*sequenceDiagram\b",
        f"{_DOCS}sequenceDiagram.html",
        typed_model=True,
        native_backend=True,
    ),
    MermaidSyntaxFamily(
        "class",
        "Class Diagram",
        r"^\s*classDiagram(?:-v2)?\b",
        f"{_DOCS}classDiagram.html",
        typed_model=True,
        native_backend=True,
    ),
    MermaidSyntaxFamily(
        "state",
        "State Diagram",
        r"^\s*stateDiagram(?:-v2)?\b",
        f"{_DOCS}stateDiagram.html",
        typed_model=True,
        native_backend=True,
    ),
    MermaidSyntaxFamily(
        "er",
        "Entity Relationship Diagram",
        r"^\s*erDiagram\b",
        f"{_DOCS}entityRelationshipDiagram.html",
        typed_model=True,
        native_backend=True,
    ),
    MermaidSyntaxFamily("journey", "User Journey", r"^\s*journey\b", f"{_DOCS}userJourney.html"),
    MermaidSyntaxFamily("gantt", "Gantt", r"^\s*gantt\b", f"{_DOCS}gantt.html"),
    MermaidSyntaxFamily("pie", "Pie Chart", r"^\s*pie\b", f"{_DOCS}pie.html"),
    MermaidSyntaxFamily(
        "quadrant",
        "Quadrant Chart",
        r"^\s*quadrantChart\b",
        f"{_DOCS}quadrantChart.html",
    ),
    MermaidSyntaxFamily(
        "requirement",
        "Requirement Diagram",
        r"^\s*requirement(?:Diagram)?\b",
        f"{_DOCS}requirementDiagram.html",
    ),
    MermaidSyntaxFamily("gitgraph", "GitGraph", r"^\s*gitGraph\b", f"{_DOCS}gitgraph.html"),
    MermaidSyntaxFamily(
        "c4",
        "C4 Diagram",
        r"^\s*C4(?:Context|Container|Component|Dynamic|Deployment)\b",
        f"{_DOCS}c4.html",
        experimental=True,
    ),
    MermaidSyntaxFamily("mindmap", "Mindmap", r"^\s*mindmap\b", f"{_DOCS}mindmap.html"),
    MermaidSyntaxFamily("timeline", "Timeline", r"^\s*timeline\b", f"{_DOCS}timeline.html"),
    MermaidSyntaxFamily("zenuml", "ZenUML", r"^\s*zenuml\b", f"{_DOCS}zenuml.html"),
    MermaidSyntaxFamily(
        "sankey",
        "Sankey",
        r"^\s*sankey(?:-beta)?\b",
        f"{_DOCS}sankey.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "xychart",
        "XY Chart",
        r"^\s*xychart(?:-beta)?\b",
        f"{_DOCS}xyChart.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "block",
        "Block Diagram",
        r"^\s*block(?:-beta)?\b",
        f"{_DOCS}block.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "packet",
        "Packet Diagram",
        r"^\s*packet(?:-beta)?\b",
        f"{_DOCS}packet.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "kanban",
        "Kanban",
        r"^\s*kanban\b",
        f"{_DOCS}kanban.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "architecture",
        "Architecture Diagram",
        r"^\s*architecture\b",
        f"{_DOCS}architecture.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "radar",
        "Radar",
        r"^\s*radar-beta\b",
        f"{_DOCS}radar.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "eventmodeling",
        "Event Modeling",
        r"^\s*eventmodeling\b",
        f"{_DOCS}eventmodeling.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "treemap",
        "Treemap",
        r"^\s*treemap\b",
        f"{_DOCS}treemap.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "venn",
        "Venn",
        r"^\s*venn-beta\b",
        f"{_DOCS}venn.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "ishikawa",
        "Ishikawa",
        r"^\s*ishikawa(?:-beta)?\b",
        f"{_DOCS}ishikawa.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "wardley",
        "Wardley Map",
        r"^\s*wardley-beta\b",
        f"{_DOCS}wardley.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "cynefin",
        "Cynefin",
        r"^\s*cynefin-beta(?:[\s:]|$)",
        f"{_DOCS}cynefin.html",
        experimental=True,
    ),
    MermaidSyntaxFamily(
        "treeview",
        "TreeView",
        r"^\s*treeView-beta\b",
        f"{_DOCS}treeView.html",
        experimental=True,
    ),
    # Mermaid 11.16 ships four Railroad detectors and a syntax page, but the
    # family is not yet linked from the public Diagram Syntax navigation.
    MermaidSyntaxFamily(
        "railroad",
        "Railroad",
        r"^\s*railroad(?:-(?:ebnf|abnf|peg))?-beta\b",
        f"{_DOCS}railroad.html",
        experimental=True,
    ),
)

MERMAID_SOURCE_ONLY_KINDS = frozenset(
    family.kind for family in MERMAID_SYNTAX_FAMILIES if not family.typed_model
)
MERMAID_NATIVE_KINDS = frozenset(
    family.kind for family in MERMAID_SYNTAX_FAMILIES if family.native_backend
)


def detect_mermaid_family(header: str) -> MermaidSyntaxFamily | None:
    """Return the registered family matching a Mermaid declaration line."""

    for family in MERMAID_SYNTAX_FAMILIES:
        if family.matches(header):
            return family
    return None


def mermaid_support_rows() -> list[dict[str, object]]:
    """Return the compatibility registry as JSON-safe records."""

    return [
        {
            "kind": family.kind,
            "title": family.title,
            "documentation": family.documentation,
            "typed_model": family.typed_model,
            "native_backend": family.native_backend,
            "official_backend": True,
            "experimental": family.experimental,
        }
        for family in MERMAID_SYNTAX_FAMILIES
    ]
