# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from .model import Direction


def choose_additional_anchors(root):
    usage = {node: {direction: set() for direction in Direction} for node in walk(root)}
    for node in walk(root):
        for connector in node.top_connectors + node.bottom_connectors + node.left_connectors + node.right_connectors:
            usage[node][connector.direction].add(connector.reference.reference_type)
    for reference in root.additional_references:
        reference.source_anchor = reference.source_anchor or preferred(reference.source, reference.target)
        reference.target_anchor = reference.target_anchor or preferred(reference.target, reference.source)
        usage[reference.source][reference.source_anchor].add(reference.reference_type)
        usage[reference.target][reference.target_anchor].add(reference.reference_type)


def preferred(source, target):
    dx = target.cx - source.cx
    dy = target.cy - source.cy
    if abs(dx) >= abs(dy):
        return Direction.RIGHT if dx >= 0 else Direction.LEFT
    return Direction.BOTTOM if dy >= 0 else Direction.TOP


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)
