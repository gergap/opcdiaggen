# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from .model import Direction, Reference

try:
    import _libavoid_py11 as _adaptagrams
except ImportError:
    _adaptagrams = None

MIN_SPACING = 20


def anchor(node, direction):
    if direction == Direction.LEFT:
        return node.x, node.cy
    if direction == Direction.RIGHT:
        return node.x + node.w, node.cy
    if direction == Direction.TOP:
        return node.cx, node.y
    return node.cx, node.bottom


class AdditionalReferenceRouter:
    """Routing boundary for non-hierarchical references."""

    def route(self, references, nodes, fixed_paths=()):
        raise NotImplementedError


class LibavoidRouter(AdditionalReferenceRouter):
    def route(self, references, nodes, fixed_paths=()):
        if not references:
            return {}
        if _adaptagrams is None:
            return {reference: self._fallback(reference) for reference in references}
        rectangles = [_adaptagrams.Rectangle(node.x, node.y, node.w, node.h) for node in nodes]
        indices = {node: index for index, node in enumerate(nodes)}
        connections = []
        for reference in references:
            sx, sy = anchor(reference.source, reference.source_anchor)
            tx, ty = anchor(reference.target, reference.target_anchor)
            connections.append(_adaptagrams.Connection(
                indices[reference.source], indices[reference.target], sx, sy, tx, ty,
                self._native_direction(reference.source_anchor),
                self._native_direction(reference.target_anchor),
            ))
        try:
            routes = _adaptagrams.route(
                rectangles, connections, fixed_paths,
                shape_buffer_distance=MIN_SPACING,
                ideal_nudging_distance=MIN_SPACING,
                segment_penalty=10.0,
                crossing_penalty=10000.0,
            )
        except Exception:
            return {reference: self._fallback(reference) for reference in references}
        return dict(zip(references, routes))

    @staticmethod
    def _native_direction(direction):
        return {
            Direction.LEFT: _adaptagrams.CONN_DIR_LEFT,
            Direction.RIGHT: _adaptagrams.CONN_DIR_RIGHT,
            Direction.TOP: _adaptagrams.CONN_DIR_UP,
            Direction.BOTTOM: _adaptagrams.CONN_DIR_DOWN,
        }[direction]

    @staticmethod
    def _fallback(reference):
        source = anchor(reference.source, reference.source_anchor)
        target = anchor(reference.target, reference.target_anchor)
        if reference.source_anchor in (Direction.LEFT, Direction.RIGHT):
            mid_x = (source[0] + target[0]) / 2
            return [source, (mid_x, source[1]), (mid_x, target[1]), target]
        mid_y = (source[1] + target[1]) / 2
        return [source, (source[0], mid_y), (target[0], mid_y), target]
