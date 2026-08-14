# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass, field
from enum import Enum


class Direction(Enum):
    TOP = "t"
    BOTTOM = "b"
    LEFT = "l"
    RIGHT = "r"


@dataclass(eq=False)
class Reference:
    reference_type: str
    source: "Node"
    target: "Node"
    hierarchical: bool = False
    source_direction: Direction | None = None
    target_direction: Direction | None = None
    source_anchor: Direction | None = None
    target_anchor: Direction | None = None


@dataclass(eq=False)
class Junction:
    node: "Node"
    direction: Direction
    references: list[Reference] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0


@dataclass(eq=False)
class Connector:
    node: "Node"
    direction: Direction
    reference: Reference
    outgoing: bool
    junction: Junction | None = None


@dataclass
class Style:
    fill: str = "#e6ecf7"
    instance_fill_start: str = "#ffffff"
    instance_fill_end: str = "#f0f0f0"
    type_fill: str = "#e8eef7"
    stroke: str = "#404040"
    text: str = "#000000"
    font: str = "Helvetica"
    arrow: str = "#404040"
    stroke_width: float = 1.3
    min_width: float = 230


@dataclass(eq=False)
class Node:
    label: str
    nodeclass: str = "objtype"
    reference_type: str | None = None
    branch_group: int = 0
    node_id: str | None = None
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    outgoing_references: list[Reference] = field(default_factory=list)
    top_connectors: list[Connector] = field(default_factory=list)
    bottom_connectors: list[Connector] = field(default_factory=list)
    left_connectors: list[Connector] = field(default_factory=list)
    right_connectors: list[Connector] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    subtree_left: float = 0.0
    subtree_top: float = 0.0
    subtree_right: float = 0.0
    subtree_bottom: float = 0.0
    style: Style = field(default_factory=Style)
    additional_references: list[Reference] = field(default_factory=list)
    junctions: list[Junction] = field(default_factory=list)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def connectors(self):
        return {
            Direction.TOP: self.top_connectors,
            Direction.BOTTOM: self.bottom_connectors,
            Direction.LEFT: self.left_connectors,
            Direction.RIGHT: self.right_connectors,
        }

    def add_child(self, child: "Node"):
        child.parent = self
        self.children.append(child)

    def add_connector(self, connector: Connector):
        self.connectors[connector.direction].append(connector)


def infer_reference_type(source_class, destination_class):
    if source_class == "objtype" and destination_class == "obj":
        return "hasTypeDefinition"
    if source_class == "obj" and destination_class == "obj":
        return "hasComponent"
    if source_class in ("obj", "objtype") and destination_class in ("var", "vartype"):
        return "hasProperty"
    return "inheritance"
