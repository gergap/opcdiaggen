# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from .base import MAX_GROUPS_PER_ROW, MIN_SPACING, Layout, set_box, translate


class StructuralLayout(Layout):
    """Places structural children in centered rows below their parent."""

    def layout(self, node, x, y, context):
        set_box(node, x, y)
        prepared = []
        for child in node.children:
            context.selector(child).layout(child, 0, 0, context)
            prepared.append((child, child.subtree_right - child.subtree_left,
                             child.subtree_bottom - child.subtree_top))
        for row_start in range(0, len(prepared), MAX_GROUPS_PER_ROW):
            row = prepared[row_start:row_start + MAX_GROUPS_PER_ROW]
            row_width = sum(item[1] for item in row) + MIN_SPACING * (len(row) - 1)
            row_x = node.cx - row_width / 2
            row_y = node.subtree_bottom + 40
            row_height = max((item[2] for item in row), default=0)
            for child, width, _ in row:
                translate(child, row_x - child.subtree_left, row_y - child.subtree_top)
                node.subtree_left = min(node.subtree_left, child.subtree_left)
                node.subtree_right = max(node.subtree_right, child.subtree_right)
                node.subtree_bottom = max(node.subtree_bottom, child.subtree_bottom)
                row_x += width + MIN_SPACING
            node.subtree_bottom = max(node.subtree_bottom, row_y + row_height)
        return node.subtree_right - node.subtree_left, node.subtree_bottom - node.subtree_top
