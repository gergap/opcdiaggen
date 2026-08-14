# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from abc import ABC, abstractmethod

BOX_H = 40
ROOT_X, ROOT_Y = 298, 4
MIN_SPACING = 20
MAX_GROUPS_PER_ROW = 2
CANVAS_W, CANVAS_H = 837, 550
VERTICAL_REFERENCES = {"hasProperty", "hasComponent", "Organizes"}


def label_width(label):
    return max((len(line) * 7.2 for line in label.split("\n")), default=0)


def set_box(node, x, y):
    node.w = max(node.style.min_width, label_width(node.label) + 24)
    node.h = BOX_H
    node.x, node.y = x, y
    node.subtree_left = x
    node.subtree_top = y
    node.subtree_right = x + node.w
    node.subtree_bottom = y + node.h


def translate(node, dx, dy):
    node.x += dx
    node.y += dy
    node.subtree_left += dx
    node.subtree_right += dx
    node.subtree_top += dy
    node.subtree_bottom += dy
    for child in node.children:
        translate(child, dx, dy)


class Layout(ABC):
    """Strategy for placing one subtree."""

    @abstractmethod
    def layout(self, node, x, y, context):
        raise NotImplementedError


class LayoutContext:
    def __init__(self, selector):
        self.selector = selector
