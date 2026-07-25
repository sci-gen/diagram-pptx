"""A deterministic Sugiyama-inspired layered layout for flowcharts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

import networkx as nx

from ..model import (
    Diagram,
    DiagramLayout,
    DiagramNode,
    Point,
    PositionedGroup,
    PositionedNode,
    RoutedEdge,
)


@dataclass(slots=True)
class LayeredLayout:
    """Lay out a directed graph in ranks with orthogonal edge routes.

    The implementation intentionally owns only a compact, deterministic MVP.
    Callers can replace it through the ``LayoutEngine`` protocol when they need
    Graphviz, ELK, or a domain-specific algorithm.
    """

    rank_spacing: float = 1.0
    node_spacing: float = 0.65
    group_padding: float = 0.35
    min_node_width: float = 1.8
    max_node_width: float = 3.4
    min_node_height: float = 0.85
    crossing_reduction_sweeps: int = 6

    def apply(self, diagram: Diagram) -> DiagramLayout:
        diagram.validate()
        if not diagram.nodes:
            return DiagramLayout([], [], width=0, height=0, direction=diagram.direction)

        ranks = self._assign_ranks(diagram)
        ordered_ranks = self._order_ranks(diagram, ranks)
        dimensions = {node.id: self._node_size(node) for node in diagram.nodes}
        positioned, primary_extent, secondary_extent = self._place_nodes(
            diagram, ordered_ranks, dimensions
        )
        node_map = {node.node.id: node for node in positioned}
        routed = [
            RoutedEdge(
                edge=edge,
                points=self._route_edge(edge.source, edge.target, node_map, diagram.direction),
            )
            for edge in diagram.edges
        ]
        groups = self._position_groups(diagram, node_map)
        width, height = self._physical_extents(diagram.direction, primary_extent, secondary_extent)
        return DiagramLayout(
            nodes=positioned,
            edges=routed,
            groups=groups,
            width=width,
            height=height,
            direction=diagram.direction,
            metadata={"engine": "layered", "rank_count": len(ordered_ranks)},
        )

    @staticmethod
    def _assign_ranks(diagram: Diagram) -> dict[str, int]:
        graph = nx.DiGraph()
        graph.add_nodes_from(node.id for node in diagram.nodes)
        graph.add_edges_from((edge.source, edge.target) for edge in diagram.edges)

        components = list(nx.strongly_connected_components(graph))
        component_by_node = {
            node_id: component_index
            for component_index, component in enumerate(components)
            for node_id in component
        }
        condensed = nx.DiGraph()
        condensed.add_nodes_from(range(len(components)))
        for source, target in graph.edges:
            source_component = component_by_node[source]
            target_component = component_by_node[target]
            if source_component != target_component:
                condensed.add_edge(source_component, target_component)

        component_rank: dict[int, int] = {}
        for component in nx.topological_sort(condensed):
            predecessors = list(condensed.predecessors(component))
            component_rank[component] = (
                max(component_rank[pred] + len(components[pred]) for pred in predecessors)
                if predecessors
                else 0
            )

        input_index = {node.id: index for index, node in enumerate(diagram.nodes)}
        rank_by_node: dict[str, int] = {}
        for component_index, component in enumerate(components):
            base_rank = component_rank[component_index]
            # A cycle cannot have a true layered ordering. Spread its members
            # deterministically over adjacent ranks to keep the drawing legible.
            for cycle_offset, node_id in enumerate(
                sorted(component, key=lambda item: input_index[item])
            ):
                rank_by_node[node_id] = base_rank + cycle_offset
        return rank_by_node

    def _order_ranks(self, diagram: Diagram, ranks: dict[str, int]) -> dict[int, list[str]]:
        input_index = {node.id: index for index, node in enumerate(diagram.nodes)}
        by_rank: dict[int, list[str]] = defaultdict(list)
        for node in diagram.nodes:
            by_rank[ranks[node.id]].append(node.id)
        for rank_nodes in by_rank.values():
            rank_nodes.sort(key=input_index.__getitem__)

        predecessors: dict[str, list[str]] = defaultdict(list)
        successors: dict[str, list[str]] = defaultdict(list)
        for edge in diagram.edges:
            successors[edge.source].append(edge.target)
            predecessors[edge.target].append(edge.source)

        rank_numbers = sorted(by_rank)
        for sweep in range(self.crossing_reduction_sweeps):
            downward = sweep % 2 == 0
            traversal = rank_numbers[1:] if downward else reversed(rank_numbers[:-1])
            neighbors = predecessors if downward else successors
            for rank in traversal:
                reference_positions = {
                    node_id: order
                    for adjacent_rank in rank_numbers
                    for order, node_id in enumerate(by_rank[adjacent_rank])
                }

                def barycenter(
                    node_id: str,
                    positions: dict[str, int] = reference_positions,
                    adjacent_nodes: dict[str, list[str]] = neighbors,
                ) -> tuple[float, int]:
                    adjacent = [
                        positions[item] for item in adjacent_nodes[node_id] if item in positions
                    ]
                    return (
                        mean(adjacent) if adjacent else float(input_index[node_id]),
                        input_index[node_id],
                    )

                by_rank[rank].sort(key=barycenter)
        return dict(by_rank)

    def _place_nodes(
        self,
        diagram: Diagram,
        ordered_ranks: dict[int, list[str]],
        dimensions: dict[str, tuple[float, float]],
    ) -> tuple[list[PositionedNode], float, float]:
        horizontal = diagram.direction in {"LR", "RL"}
        nodes_by_id = diagram.node_map()
        rank_numbers = sorted(ordered_ranks)
        rank_primary_sizes: dict[int, float] = {}
        rank_secondary_sizes: dict[int, float] = {}

        for rank in rank_numbers:
            node_ids = ordered_ranks[rank]
            primary_sizes = [dimensions[node_id][0 if horizontal else 1] for node_id in node_ids]
            secondary_sizes = [dimensions[node_id][1 if horizontal else 0] for node_id in node_ids]
            rank_primary_sizes[rank] = max(primary_sizes, default=0)
            rank_secondary_sizes[rank] = sum(secondary_sizes) + self.node_spacing * max(
                len(node_ids) - 1, 0
            )

        secondary_extent = max(rank_secondary_sizes.values(), default=0)
        primary_offsets: dict[int, float] = {}
        primary_cursor = 0.0
        for rank in rank_numbers:
            primary_offsets[rank] = primary_cursor
            primary_cursor += rank_primary_sizes[rank] + self.rank_spacing
        primary_extent = max(primary_cursor - self.rank_spacing, 0)

        positioned: list[PositionedNode] = []
        for rank in rank_numbers:
            secondary_cursor = (secondary_extent - rank_secondary_sizes[rank]) / 2
            for order, node_id in enumerate(ordered_ranks[rank]):
                width, height = dimensions[node_id]
                primary_size = width if horizontal else height
                secondary_size = height if horizontal else width
                primary = primary_offsets[rank] + (rank_primary_sizes[rank] - primary_size) / 2
                secondary = secondary_cursor
                x, y = self._to_physical_position(
                    diagram.direction,
                    primary,
                    secondary,
                    primary_size,
                    secondary_size,
                    primary_extent,
                )
                positioned.append(
                    PositionedNode(
                        node=nodes_by_id[node_id],
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                        rank=rank,
                        order=order,
                    )
                )
                secondary_cursor += secondary_size + self.node_spacing
        return positioned, primary_extent, secondary_extent

    @staticmethod
    def _to_physical_position(
        direction: str,
        primary: float,
        secondary: float,
        primary_size: float,
        secondary_size: float,
        primary_extent: float,
    ) -> tuple[float, float]:
        if direction == "LR":
            return primary, secondary
        if direction == "RL":
            return primary_extent - primary - primary_size, secondary
        if direction == "TB":
            return secondary, primary
        return secondary, primary_extent - primary - primary_size

    @staticmethod
    def _physical_extents(
        direction: str, primary_extent: float, secondary_extent: float
    ) -> tuple[float, float]:
        if direction in {"LR", "RL"}:
            return primary_extent, secondary_extent
        return secondary_extent, primary_extent

    def _node_size(self, node: DiagramNode) -> tuple[float, float]:
        lines = node.label.splitlines() or [""]
        longest = max(len(line) for line in lines)
        width = min(self.max_node_width, max(self.min_node_width, 1.05 + longest * 0.105))
        height = max(self.min_node_height, 0.58 + len(lines) * 0.28)
        if node.shape.value in {"diamond", "hexagon"}:
            width = max(width, 2.1)
            height = max(height, 1.05)
        elif node.shape.value == "ellipse":
            # Curved sides reduce the usable text area more than the bounding
            # box suggests in both PowerPoint and LibreOffice.
            width = max(width, 3.2)
            height = max(height, 1.05)
        width = float(node.metadata.get("width", width))
        height = float(node.metadata.get("height", height))
        return width, height

    @staticmethod
    def _route_edge(
        source_id: str,
        target_id: str,
        nodes: dict[str, PositionedNode],
        direction: str,
    ) -> list[Point]:
        source = nodes[source_id]
        target = nodes[target_id]
        horizontal = direction in {"LR", "RL"}

        if source_id == target_id:
            loop_gap = 0.5
            if horizontal:
                start = Point(source.x + source.width, source.center.y)
                end = Point(source.x, source.center.y)
                loop_y = source.y - loop_gap
                return [
                    start,
                    Point(source.x + source.width + loop_gap, start.y),
                    Point(source.x + source.width + loop_gap, loop_y),
                    Point(source.x - loop_gap, loop_y),
                    Point(source.x - loop_gap, end.y),
                    end,
                ]
            start = Point(source.center.x, source.y + source.height)
            end = Point(source.center.x, source.y)
            loop_x = source.x + source.width + loop_gap
            return [
                start,
                Point(start.x, source.y + source.height + loop_gap),
                Point(loop_x, source.y + source.height + loop_gap),
                Point(loop_x, source.y - loop_gap),
                Point(end.x, source.y - loop_gap),
                end,
            ]

        if horizontal:
            forward = target.center.x >= source.center.x
            start = Point(source.x + source.width if forward else source.x, source.center.y)
            end = Point(target.x if forward else target.x + target.width, target.center.y)
            middle = (start.x + end.x) / 2
            points = [start, Point(middle, start.y), Point(middle, end.y), end]
        else:
            forward = target.center.y >= source.center.y
            start = Point(source.center.x, source.y + source.height if forward else source.y)
            end = Point(target.center.x, target.y if forward else target.y + target.height)
            middle = (start.y + end.y) / 2
            points = [start, Point(start.x, middle), Point(end.x, middle), end]
        return LayeredLayout._deduplicate_points(points)

    @staticmethod
    def _deduplicate_points(points: list[Point]) -> list[Point]:
        result: list[Point] = []
        for point in points:
            if not result or point != result[-1]:
                result.append(point)
        return result

    def _position_groups(
        self, diagram: Diagram, nodes: dict[str, PositionedNode]
    ) -> list[PositionedGroup]:
        positioned: list[PositionedGroup] = []
        for group in diagram.groups:
            members = [nodes[node_id] for node_id in group.node_ids if node_id in nodes]
            if not members:
                continue
            left = min(node.x for node in members) - self.group_padding
            top = min(node.y for node in members) - self.group_padding - 0.18
            right = max(node.x + node.width for node in members) + self.group_padding
            bottom = max(node.y + node.height for node in members) + self.group_padding
            positioned.append(PositionedGroup(group, left, top, right - left, bottom - top))
        # Parents first so nested groups paint on top in predictable order.
        depth_by_id: dict[str, int] = {}
        group_by_id = {group.id: group for group in diagram.groups}

        def depth(group_id: str) -> int:
            if group_id not in depth_by_id:
                parent = group_by_id[group_id].parent_id
                depth_by_id[group_id] = 0 if parent is None else depth(parent) + 1
            return depth_by_id[group_id]

        positioned.sort(key=lambda item: depth(item.group.id))
        return positioned
