"""JSON/dict importer for the public diagram interchange schema."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..model import Diagram, DiagramEdge, DiagramGroup, DiagramNode, NodeShape


class JsonImporter:
    """Import a diagram from a JSON string, bytes, or mapping."""

    def parse(self, source: str | bytes | Mapping[str, Any]) -> Diagram:
        data: Mapping[str, Any]
        if isinstance(source, Mapping):
            data = source
        else:
            parsed = json.loads(source)
            if not isinstance(parsed, Mapping):
                raise ValueError("The JSON root must be an object")
            data = parsed

        nodes = [
            DiagramNode(
                id=str(item["id"]),
                label=str(item.get("label", item["id"])),
                shape=NodeShape(item.get("shape", NodeShape.RECTANGLE.value)),
                style=dict(item.get("style", {})),
                metadata=dict(item.get("metadata", {})),
                group_id=item.get("group_id"),
            )
            for item in data.get("nodes", [])
        ]
        edges = [
            DiagramEdge(
                source=str(item["source"]),
                target=str(item["target"]),
                label=item.get("label"),
                directed=bool(item.get("directed", True)),
                style=dict(item.get("style", {})),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("edges", [])
        ]
        groups = [
            DiagramGroup(
                id=str(item["id"]),
                label=str(item.get("label", item["id"])),
                node_ids=[str(node_id) for node_id in item.get("node_ids", [])],
                parent_id=item.get("parent_id"),
                style=dict(item.get("style", {})),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("groups", [])
        ]
        diagram = Diagram(
            nodes=nodes,
            edges=edges,
            groups=groups,
            direction=str(data.get("direction", "LR")).upper(),
            metadata=dict(data.get("metadata", {})),
        )
        diagram.validate()
        return diagram
