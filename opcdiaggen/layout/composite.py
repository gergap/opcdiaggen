# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from .aggregate import AggregateLayout
from .base import VERTICAL_REFERENCES
from .structural import StructuralLayout


class CompositeLayout:
    """Selects a layout strategy independently for every subtree."""

    def __init__(self, aggregate=None, structural=None):
        self.aggregate = aggregate or AggregateLayout()
        self.structural = structural or StructuralLayout()

    def __call__(self, node):
        if not node.children or all(child.reference_type in VERTICAL_REFERENCES for child in node.children):
            return self.aggregate
        return self.structural
