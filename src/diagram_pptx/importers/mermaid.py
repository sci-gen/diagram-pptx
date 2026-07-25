"""A deliberately small Mermaid flowchart importer.

This is not a Mermaid renderer. It converts the useful semantic subset into
the package's stable IR so that layout and output stay backend-independent.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Any

from ..model import Diagram, DiagramEdge, DiagramGroup, DiagramNode, NodeShape

_HEADER_RE = re.compile(r"^(?:flowchart|graph)\s+(LR|RL|TB|TD|BT)\s*$", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*")
_EDGE_TOKEN_RE = re.compile(r"\s*(-->|---|==>|-\.->)\s*")
_PIPE_LABEL_RE = re.compile(r"^\|([^|]*)\|\s*")
_CLASS_DEF_RE = re.compile(r"^classDef\s+([A-Za-z_][\w-]*)\s+(.+)$")
_CLASS_RE = re.compile(r"^class\s+([\w,-]+)\s+([A-Za-z_][\w-]*)\s*$")
_STYLE_RE = re.compile(r"^style\s+([A-Za-z_][\w-]*)\s+(.+)$")
_SUBGRAPH_RE = re.compile(r"^subgraph\s+(.+)$", re.IGNORECASE)


class MermaidParseError(ValueError):
    """Raised when input is outside the supported flowchart subset."""


@dataclass(slots=True)
class _GroupBuilder:
    id: str
    label: str
    parent_id: str | None
    node_ids: list[str] = field(default_factory=list)


class MermaidFlowchartImporter:
    """Parse common Mermaid flowchart syntax into :class:`Diagram`.

    Supported:
    - ``flowchart`` / ``graph`` with LR, RL, TB/TD, or BT direction
    - rectangle, rounded, decision, circle, stadium, subprocess, and hexagon nodes
    - ``-->``, ``---``, ``==>``, ``-.->`` and ``-->|label|`` edges
    - chained edges
    - subgraphs (including nesting)
    - ``classDef``, ``class``, and per-node ``style``
    """

    def parse(self, source: str) -> Diagram:
        if not isinstance(source, str):
            raise TypeError("Mermaid source must be text")

        lines = self._logical_lines(source)
        if not lines:
            raise MermaidParseError("Mermaid source is empty")
        header = _HEADER_RE.match(lines[0])
        if not header:
            raise MermaidParseError(
                "Expected a flowchart header such as 'flowchart LR'; "
                "only Mermaid flowcharts are supported"
            )

        direction = header.group(1).upper().replace("TD", "TB")
        nodes: dict[str, DiagramNode] = {}
        edges: list[DiagramEdge] = []
        group_builders: dict[str, _GroupBuilder] = {}
        group_stack: list[str] = []
        class_defs: dict[str, dict[str, Any]] = {}
        class_memberships: list[tuple[list[str], str]] = []
        node_styles: list[tuple[str, dict[str, Any]]] = []

        for line_number, statement in enumerate(lines[1:], start=2):
            if statement.lower() == "end":
                if not group_stack:
                    raise MermaidParseError(f"Line {line_number}: unmatched 'end'")
                group_stack.pop()
                continue

            subgraph_match = _SUBGRAPH_RE.match(statement)
            if subgraph_match:
                group_id, label = self._parse_subgraph(subgraph_match.group(1), line_number)
                if group_id in group_builders:
                    raise MermaidParseError(
                        f"Line {line_number}: duplicate subgraph id {group_id!r}"
                    )
                parent_id = group_stack[-1] if group_stack else None
                group_builders[group_id] = _GroupBuilder(group_id, label, parent_id)
                group_stack.append(group_id)
                continue

            class_def = _CLASS_DEF_RE.match(statement)
            if class_def:
                class_defs[class_def.group(1)] = self._parse_style(class_def.group(2))
                continue

            class_assignment = _CLASS_RE.match(statement)
            if class_assignment:
                class_memberships.append(
                    (class_assignment.group(1).split(","), class_assignment.group(2))
                )
                continue

            style_assignment = _STYLE_RE.match(statement)
            if style_assignment:
                node_styles.append(
                    (style_assignment.group(1), self._parse_style(style_assignment.group(2)))
                )
                continue

            if statement.lower().startswith(("click ", "linkStyle ", "direction ")):
                # Interaction, global link styling, and nested direction do not alter the IR yet.
                continue

            try:
                parsed_nodes, parsed_edges = self._parse_graph_statement(statement)
            except MermaidParseError as exc:
                raise MermaidParseError(f"Line {line_number}: {exc}") from exc

            current_group = group_stack[-1] if group_stack else None
            for parsed in parsed_nodes:
                self._upsert_node(nodes, parsed, current_group)
                for group_id in group_stack:
                    builder = group_builders[group_id]
                    if parsed.id not in builder.node_ids:
                        builder.node_ids.append(parsed.id)
            edges.extend(parsed_edges)

        if group_stack:
            raise MermaidParseError(f"Unclosed subgraph: {group_stack[-1]!r}")

        for node_ids, class_name in class_memberships:
            if class_name not in class_defs:
                raise MermaidParseError(f"Unknown classDef {class_name!r}")
            for node_id in node_ids:
                if node_id not in nodes:
                    nodes[node_id] = DiagramNode(node_id, node_id)
                nodes[node_id].style.update(class_defs[class_name])
                nodes[node_id].metadata.setdefault("classes", []).append(class_name)

        for node_id, style in node_styles:
            if node_id not in nodes:
                nodes[node_id] = DiagramNode(node_id, node_id)
            nodes[node_id].style.update(style)

        groups = [
            DiagramGroup(
                id=builder.id,
                label=builder.label,
                node_ids=builder.node_ids,
                parent_id=builder.parent_id,
            )
            for builder in group_builders.values()
        ]
        diagram = Diagram(
            nodes=list(nodes.values()),
            edges=edges,
            groups=groups,
            direction=direction,
            metadata={"source_format": "mermaid-flowchart"},
        )
        diagram.validate()
        return diagram

    @staticmethod
    def _logical_lines(source: str) -> list[str]:
        statements: list[str] = []
        for raw_line in source.replace("\r\n", "\n").split("\n"):
            line = raw_line.split("%%", 1)[0].strip()
            if not line or line == "---" or line.startswith("title:"):
                continue
            # Mermaid accepts semicolon-separated statements. This intentionally
            # leaves semicolons inside quoted labels untouched.
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";")
            lexer.whitespace_split = True
            lexer.commenters = ""
            parts: list[str] = []
            current: list[str] = []
            for token in lexer:
                if token == ";":
                    if current:
                        parts.append(" ".join(current))
                        current = []
                else:
                    current.append(token)
            if current:
                parts.append(" ".join(current))
            statements.extend(part.strip() for part in parts if part.strip())
        return statements

    def _parse_graph_statement(self, statement: str) -> tuple[list[DiagramNode], list[DiagramEdge]]:
        statement = re.sub(
            r"--\s+([^|<>]+?)\s+-->",
            lambda match: f"-->|{match.group(1).strip()}|",
            statement,
        )
        first, offset = self._parse_node_expression(statement, 0)
        nodes = [first]
        edges: list[DiagramEdge] = []
        cursor = offset

        while cursor < len(statement):
            remaining = statement[cursor:]
            edge_match = _EDGE_TOKEN_RE.match(remaining)
            if not edge_match:
                # A node-only statement must have no unparsed content.
                if remaining.strip():
                    raise MermaidParseError(f"Unsupported syntax near {remaining.strip()!r}")
                break
            token = edge_match.group(1)
            cursor += edge_match.end()
            label: str | None = None

            pipe_match = _PIPE_LABEL_RE.match(statement[cursor:])
            if pipe_match:
                label = self._clean_label(pipe_match.group(1))
                cursor += pipe_match.end()

            target, cursor = self._parse_node_expression(statement, cursor)
            nodes.append(target)
            style: dict[str, Any] = {}
            if token == "-.->":
                style["dash"] = "dash"
            elif token == "==>":
                style["width"] = 2.5
            edges.append(
                DiagramEdge(
                    source=nodes[-2].id,
                    target=target.id,
                    label=label,
                    directed=token != "---",
                    style=style,
                )
            )
        return nodes, edges

    def _parse_node_expression(self, text: str, offset: int) -> tuple[DiagramNode, int]:
        match = _IDENTIFIER_RE.match(text[offset:].lstrip())
        leading = len(text[offset:]) - len(text[offset:].lstrip())
        if not match:
            raise MermaidParseError(f"Expected a node near {text[offset:].strip()!r}")
        node_id = match.group(0)
        cursor = offset + leading + match.end()
        if cursor >= len(text) or text[cursor].isspace():
            return DiagramNode(node_id, node_id), cursor

        shape, label, end = self._parse_shape_suffix(text, cursor)
        if shape is None:
            return DiagramNode(node_id, node_id), cursor
        return DiagramNode(node_id, label, shape), end

    def _parse_shape_suffix(self, text: str, cursor: int) -> tuple[NodeShape | None, str, int]:
        delimiters = [
            ("((", "))", NodeShape.ELLIPSE),
            ("([", "])", NodeShape.STADIUM),
            ("[[", "]]", NodeShape.SUBPROCESS),
            ("{{", "}}", NodeShape.HEXAGON),
            ("[", "]", NodeShape.RECTANGLE),
            ("(", ")", NodeShape.ROUNDED_RECTANGLE),
            ("{", "}", NodeShape.DIAMOND),
        ]
        for opening, closing, shape in delimiters:
            if text.startswith(opening, cursor):
                end = text.find(closing, cursor + len(opening))
                if end < 0:
                    raise MermaidParseError(f"Unclosed node shape for {text[:cursor]!r}")
                raw_label = text[cursor + len(opening) : end]
                return shape, self._clean_label(raw_label), end + len(closing)
        return None, "", cursor

    @staticmethod
    def _upsert_node(
        nodes: dict[str, DiagramNode], parsed: DiagramNode, current_group: str | None
    ) -> None:
        existing = nodes.get(parsed.id)
        if existing is None:
            parsed.group_id = current_group
            nodes[parsed.id] = parsed
            return
        if parsed.label != parsed.id or parsed.shape != NodeShape.RECTANGLE:
            existing.label = parsed.label
            existing.shape = parsed.shape
        if existing.group_id is None:
            existing.group_id = current_group

    @staticmethod
    def _parse_subgraph(spec: str, line_number: int) -> tuple[str, str]:
        spec = spec.strip()
        bracket_match = re.match(r"([A-Za-z_][\w-]*)\s*\[(.*)\]\s*$", spec)
        if bracket_match:
            return bracket_match.group(1), MermaidFlowchartImporter._clean_label(
                bracket_match.group(2)
            )
        id_match = _IDENTIFIER_RE.match(spec)
        if not id_match:
            raise MermaidParseError(f"Line {line_number}: invalid subgraph declaration")
        group_id = id_match.group(0)
        remainder = spec[id_match.end() :].strip()
        return group_id, MermaidFlowchartImporter._clean_label(remainder or group_id)

    @staticmethod
    def _parse_style(style_text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for declaration in style_text.split(","):
            if ":" not in declaration:
                continue
            key, value = (part.strip() for part in declaration.split(":", 1))
            normalized_key = {
                "fill": "fill",
                "stroke": "line",
                "color": "text",
                "stroke-width": "line_width",
                "stroke-dasharray": "dash",
            }.get(key, key.replace("-", "_"))
            if normalized_key == "line_width":
                value = re.sub(r"px$", "", value)
                try:
                    result[normalized_key] = float(value)
                except ValueError:
                    result[normalized_key] = value
            else:
                result[normalized_key] = value
        return result

    @staticmethod
    def _clean_label(label: str) -> str:
        cleaned = label.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1]
        return cleaned.replace("<br/>", "\n").replace("<br>", "\n")
