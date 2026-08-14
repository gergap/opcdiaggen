# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from .base import MIN_SPACING, Layout, set_box


class AggregateLayout(Layout):
    """Places component/property/organizes children in a vertical column."""

    def layout(self, node, x, y, context):
        set_box(node, x, y)
        child_x = node.x + node.w + MIN_SPACING
        child_y = node.bottom + MIN_SPACING
        for child in node.children:
            context.selector(child).layout(child, child_x, child_y, context)
            node.subtree_right = max(node.subtree_right, child.subtree_right)
            node.subtree_bottom = max(node.subtree_bottom, child.subtree_bottom)
            child_y = child.subtree_bottom + MIN_SPACING
        return node.subtree_right - node.subtree_left, node.subtree_bottom - node.subtree_top
