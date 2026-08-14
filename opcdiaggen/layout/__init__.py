# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from .aggregate import AggregateLayout
from .base import CANVAS_H, CANVAS_W, MIN_SPACING, Layout, LayoutContext, ROOT_X, ROOT_Y
from .composite import CompositeLayout
from ..model import Connector, Direction, Junction
from .structural import StructuralLayout


def _collect(node):
    yield node
    for child in node.children:
        yield from _collect(child)


def _add_hierarchy_connectors(node):
    node.junctions.clear()
    grouped = {}
    for child in node.children:
        reference = next(ref for ref in node.outgoing_references
                         if ref.target is child and ref.hierarchical)
        source_direction = Direction.BOTTOM
        target_direction = (Direction.LEFT if reference.reference_type in {"hasProperty", "hasComponent", "Organizes"}
                            else Direction.TOP)
        node.add_connector(Connector(node, source_direction, reference, True))
        child.add_connector(Connector(child, target_direction, reference, False))
        reference.source_direction = source_direction
        reference.target_direction = target_direction
        grouped.setdefault((source_direction, reference.reference_type), []).append(reference)
    for (direction, _), references in grouped.items():
        junction = Junction(node, direction, references)
        if direction == Direction.TOP:
            junction.x, junction.y = node.cx, node.y - MIN_SPACING
        elif direction == Direction.BOTTOM:
            junction.x, junction.y = node.cx, node.bottom + MIN_SPACING
        elif direction == Direction.LEFT:
            junction.x, junction.y = node.x - MIN_SPACING, node.cy
        else:
            junction.x, junction.y = node.x + node.w + MIN_SPACING, node.cy
        node.junctions.append(junction)
        for reference in references:
            reference_connector = next(connector for connector in node.bottom_connectors + node.top_connectors + node.left_connectors + node.right_connectors
                                       if connector.reference is reference and connector.outgoing)
            reference_connector.junction = junction
            target_connector = next(connector for connector in reference.target.top_connectors + reference.target.bottom_connectors + reference.target.left_connectors + reference.target.right_connectors
                                    if connector.reference is reference and not connector.outgoing)
            target_connector.junction = junction
    for child in node.children:
        _add_hierarchy_connectors(child)


def layout(root, strategy=None):
    strategy = strategy or CompositeLayout()
    strategy(root).layout(root, ROOT_X, ROOT_Y, LayoutContext(strategy))
    for node in _collect(root):
        for side in node.connectors.values():
            side.clear()
    _add_hierarchy_connectors(root)
    nodes = list(_collect(root))
    min_x = min(node.subtree_left for node in nodes)
    if min_x < 4:
        for node in nodes:
            node.x += 4 - min_x
            node.subtree_left += 4 - min_x
            node.subtree_right += 4 - min_x
    width = max(CANVAS_W, int(max(node.subtree_right for node in nodes) + 7))
    height = max(CANVAS_H, int(max(node.subtree_bottom for node in nodes) + 8))
    return width, height


__all__ = [
    "AggregateLayout",
    "CompositeLayout",
    "Layout",
    "LayoutContext",
    "StructuralLayout",
    "layout",
]
