#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only
#
# This file is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This file is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this file. If not, see <https://www.gnu.org/licenses/>.

"""
tree2svg.py - render an OPC UA type-system tree description directly to SVG,
with a merged trunk line per parent and a proper hollow UML inheritance
triangle - computed exactly from the layout, not reverse-engineered from
someone else's renderer.

Input syntax uses @starttypesystem/@endtypesystem markers. Node lines use
PlantUML WBS-style depth markers followed by an optional node class:

    @starttypesystem
    * objtype "BaseObjectType"
    ** objtype "STCompType"
    *** objtype "STCompRamType"
    *** objtype "STCompHeaterType"
    @endtypesystem

Supported node classes are obj, objtype, var, vartype, method, reftype,
datatype, and view. Labels must be quoted. An optional reference type can be
written before the node class; otherwise it is inferred from both classes:

    * obj "Boiler #1"
    ** hasTypeDefinition objtype "BoilerType"
    *** hasProperty var "Pressure [Double]"

The supported reference types are inheritance, hasTypeDefinition,
hasComponent, and hasProperty. In a type-system graph, an omitted node class
defaults to objtype.

Depth = number of leading '*' characters. The overview layout places the two
top-level branches below the root and sends each branch's leaves outward,
matching the reference OPC UA diagram.

Usage:
    python3 tree2svg.py input.puml -o output.svg
"""

import argparse
import html
import re
import sys
from collections import namedtuple

try:
    import _libavoid_py11 as _adaptagrams
    print("Successfully imported libavoid_py11")
except ImportError:
    print("Failed to import libavoid_py11")
    _adaptagrams = None


# --- geometry / style constants --------------------------------------------

FONT_SIZE = 12
FONT_FAMILY = "Helvetica"
MIN_BOX_W = 230
BOX_H = 40
ROOT_X, ROOT_Y = 298, 4
PARENT_Y = 122
LEAF_Y = 202
ROW_GAP = 20            # 40px node + 20px between leaf rows
PARENT_GAP = 42
MIN_HORIZONTAL_LENGTH = 40
MIN_SPACING = 20
ORGANIZES_SPACING = -20
MAX_GROUPS_PER_ROW = 2
CANVAS_W, CANVAS_H = 837, 550
FILL = "#e6ecf7"
STROKE = "#404040"
TEXT_COLOR = "#000000"
TRI_W, TRI_H = 7, 7     # inheritance triangle size in the reference export
TRI_GAP = 1.12
REFERENCE_MARKER_GAP = 6
STROKE_WIDTH = 1.3


# --- 1. parse ----------------------------------------------------------------

REFERENCE_TYPES = {
    "inheritance": "inheritance",
    "hastypedefinition": "hasTypeDefinition",
    "hascomponent": "hasComponent",
    "hasproperty": "hasProperty",
    "organizes": "Organizes",
}
REFERENCE_ORDER = ("hasTypeDefinition", "hasProperty", "hasComponent", "Organizes", "inheritance")
NODE_CLASSES = {"obj", "objtype", "var", "vartype", "method", "reftype", "datatype", "view"}
AdditionalReference = namedtuple("AdditionalReference", "reference_type source source_anchor target target_anchor")


class Node:
    __slots__ = ("label", "node_id", "nodeclass", "reference_type", "branch_group", "children", "x", "y", "w", "h", "cx", "cy",
                 "bottom", "subtree_top", "subtree_bottom", "subtree_left", "subtree_right",
                  "style", "additional_references")

    def __init__(self, label, nodeclass="objtype", reference_type=None, branch_group=0, node_id=None):
        self.label = label
        self.node_id = node_id
        self.nodeclass = nodeclass
        self.reference_type = reference_type
        self.branch_group = branch_group
        self.children = []
        self.x = self.y = self.w = self.h = 0.0
        self.cx = self.cy = self.bottom = 0.0
        self.subtree_top = self.subtree_bottom = self.subtree_left = self.subtree_right = 0.0
        self.style = {
            "fill": FILL,
            "stroke": STROKE,
            "text": TEXT_COLOR,
            "font": FONT_FAMILY,
            "arrow": STROKE,
        }
        self.additional_references = []


def parse(text):
    """Parse '*'-depth WBS syntax into a Node tree. Returns the root Node."""
    stack = []  # (depth, node)
    root = None
    style = {
        "fill": FILL,
        "instance_fill_start": "#ffffff",
        "instance_fill_end": "#f0f0f0",
        "type_fill": "#e8eef7",
        "stroke": STROKE,
        "text": TEXT_COLOR,
        "font": FONT_FAMILY,
        "arrow": STROKE,
        "stroke_width": STROKE_WIDTH,
        "min_width": MIN_BOX_W,
    }
    in_node_skinparam = False
    branch_group = 0
    pending_group_break = False
    additional_references = []
    nodes_by_id = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if root is not None:
                pending_group_break = True
            continue
        if stripped.startswith("@"):
            continue
        lower = stripped.lower()
        if lower.startswith("skinparam node {"):
            in_node_skinparam = True
            continue
        if in_node_skinparam and stripped == "}":
            in_node_skinparam = False
            continue
        ref_match = re.fullmatch(
            r"ref\s+(\S+)(?:\s+\[([tblr])\])?\s+(\S+)\s+-\s+(\S+)(?:\s+\[([tblr])\])?",
            stripped,
            re.IGNORECASE,
        )
        if ref_match:
            additional_references.append(AdditionalReference(
                ref_match.group(1), ref_match.group(3), ref_match.group(2),
                ref_match.group(4), ref_match.group(5),
            ))
            continue
        setting = re.match(r"^(?:skinparam\s+)?([A-Za-z]+)\s+(.+)$", stripped)
        if setting:
            key, value = setting.group(1).lower(), setting.group(2).strip()
            node_setting = in_node_skinparam or key.startswith("node")
            if key.startswith("node"):
                key = key[4:]
            if node_setting and key in ("backgroundcolor", "fill"):
                style["type_fill"] = value
                continue
            if node_setting and key in ("instancebackgroundcolor", "instancefill"):
                style["instance_fill_start"] = value
                continue
            if node_setting and key in ("instancebackgroundcolorend", "instancefillend"):
                style["instance_fill_end"] = value
                continue
            if node_setting and key in ("typebackgroundcolor", "typefill"):
                style["type_fill"] = value
                continue
            if node_setting and key in ("bordercolor", "stroke"):
                style["stroke"] = value
                continue
            if node_setting and key in ("strokewidth", "linewidth"):
                try:
                    stroke_width = float(value)
                except ValueError as exc:
                    raise ValueError(f"stroke width must be numeric: {value!r}") from exc
                if stroke_width <= 0:
                    raise ValueError(f"stroke width must be positive: {value!r}")
                style["stroke_width"] = stroke_width
                continue
            if node_setting and key in ("fontcolor", "textcolor"):
                style["text"] = value
                continue
            if node_setting and key in ("fontname", "fontfamily"):
                style["font"] = value
                continue
            if node_setting and key in ("minwidth", "width"):
                try:
                    min_width = float(value)
                except ValueError as exc:
                    raise ValueError(f"node minimum width must be numeric: {value!r}") from exc
                if min_width <= 0:
                    raise ValueError(f"node minimum width must be positive: {value!r}")
                style["min_width"] = min_width
                continue
            if key in ("arrowcolor", "linecolor"):
                style["arrow"] = value
                continue
        if not stripped.startswith("*"):
            continue
        m = re.match(r"^(\*+)\s*(.*)$", stripped)
        if not m:
            continue
        depth = len(m.group(1))
        content = m.group(2).strip()
        tokens = content.split(None, 2)
        explicit_reference = None
        if tokens and tokens[0].lower() in REFERENCE_TYPES:
            explicit_reference = REFERENCE_TYPES[tokens.pop(0).lower()]
        if tokens and tokens[0].lower() in NODE_CLASSES:
            nodeclass = tokens.pop(0).lower()
        else:
            nodeclass = "objtype"
        label_text = " ".join(tokens)
        label_match = re.fullmatch(
            r'"((?:[^"\\]|\\.)*)"\s*(?:\{#([A-Za-z_][A-Za-z0-9_-]*)\})?',
            label_text,
        )
        if not label_match:
            raise ValueError(f"node label must be quoted near: {stripped!r}")
        label = (label_match.group(1)
                 .replace(r'\n', '\n')
                 .replace(r'\"', '"')
                 .replace(r'\\', '\\'))
        node_id = label_match.group(2)
        node = Node(label, nodeclass, explicit_reference, branch_group, node_id)
        if node_id:
            if node_id in nodes_by_id:
                raise ValueError(f"duplicate node id: {node_id!r}")
            nodes_by_id[node_id] = node
        if depth == 1:
            root = node
            stack = [(1, node)]
            continue
        # pop stack until we find the parent (depth-1)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if not stack:
            raise ValueError(f"malformed nesting near: {stripped!r}")
        parent = stack[-1][1]
        if parent is root:
            if pending_group_break and root.children:
                branch_group += 1
            node.branch_group = branch_group
        else:
            node.branch_group = parent.branch_group
        pending_group_break = False
        if node.reference_type is None:
            node.reference_type = infer_reference_type(parent.nodeclass, node.nodeclass)
        parent.children.append(node)
        stack.append((depth, node))
    if root is None:
        raise ValueError("no root node found (expected a line starting with a single '*')")
    root.style = style
    for reference in additional_references:
        if reference.source not in nodes_by_id or reference.target not in nodes_by_id:
            raise ValueError(f"unknown node id in reference: {reference!r}")
    root.additional_references = additional_references
    return root


def infer_reference_type(source_class, destination_class):
    """Infer the common OPC UA reference for a parent-child edge.

    The tree edge is stored on the child, so an object below an object type
    points back to its type with HasTypeDefinition.
    """
    if source_class == "objtype" and destination_class == "obj":
        return "hasTypeDefinition"
    if source_class == "obj" and destination_class == "obj":
        return "hasComponent"
    if source_class == "obj" and destination_class in ("var", "vartype"):
        return "hasProperty"
    if source_class in ("obj", "objtype") and destination_class in ("var", "vartype"):
        return "hasProperty"
    return "inheritance"


# --- 2. layout ----------------------------------------------------------------

def label_width(label):
    """Estimate the rendered width of the widest label line in pixels."""
    widest = 0.0
    for line in label.split("\n"):
        width = 0.0
        for part in re.split(r"(\^[0-9]+)", line):
            if re.fullmatch(r"\^[0-9]+", part):
                width += len(part[1:]) * FONT_SIZE * 0.6 * 0.7
            else:
                width += len(part) * FONT_SIZE * 0.6
        widest = max(widest, width)
    return widest


def set_box(node, x, y, min_width):
    node.w = max(min_width, label_width(node.label) + FONT_SIZE * 2)
    node.h = BOX_H
    node.x, node.y = x, y
    node.cx, node.cy = x + node.w / 2, y + BOX_H / 2
    node.bottom = y + BOX_H
    node.subtree_top = y
    node.subtree_left = x
    node.subtree_right = x + node.w
    node.subtree_bottom = node.bottom


def layout(root):
    """Lay out aggregate members first, then subtype and instance groups."""
    min_width = root.style["min_width"]
    set_box(root, ROOT_X, ROOT_Y, min_width)

    def translate(node, dx, dy):
        node.x += dx
        node.y += dy
        node.cx += dx
        node.cy += dy
        node.bottom += dy
        node.subtree_top += dy
        node.subtree_bottom += dy
        node.subtree_left += dx
        node.subtree_right += dx
        for child in node.children:
            translate(child, dx, dy)

    def place(node, x, y):
        """Place one subtree and return its bounding-box dimensions."""
        set_box(node, x, y, min_width)
        aggregate = [child for child in node.children
                     if child.reference_type in ("hasProperty", "hasComponent")]
        organizes = [child for child in node.children
                     if child.reference_type == "Organizes"]
        structural = [child for child in node.children
                      if child not in aggregate and child not in organizes]

        if aggregate:
            child_x = node.x + node.w + MIN_SPACING
            child_y = node.bottom + MIN_SPACING
            for child in aggregate:
                place(child, child_x, child_y)
                node.subtree_right = max(node.subtree_right, child.subtree_right)
                node.subtree_bottom = max(node.subtree_bottom, child.subtree_bottom)
                child_y = child.subtree_bottom + MIN_SPACING

        if organizes:
            child_x = node.x + node.w + ORGANIZES_SPACING
            child_y = node.subtree_bottom + MIN_SPACING
            for child in organizes:
                place(child, child_x, child_y)
                node.subtree_right = max(node.subtree_right, child.subtree_right)
                node.subtree_bottom = max(node.subtree_bottom, child.subtree_bottom)
                child_y = child.subtree_bottom + MIN_SPACING

        if structural:
            prepared = []
            for child in structural:
                place(child, 0, 0)
                prepared.append((child, child.subtree_right - child.subtree_left,
                                 child.subtree_bottom - child.subtree_top))

            for row_start in range(0, len(prepared), MAX_GROUPS_PER_ROW):
                row = prepared[row_start:row_start + MAX_GROUPS_PER_ROW]
                row_width = sum(item[1] for item in row) + MIN_SPACING * (len(row) - 1)
                row_x = node.cx - row_width / 2
                edge_clearance = 2 * MIN_SPACING
                if any(child.reference_type == "inheritance" for child, _, _ in row):
                    edge_clearance += TRI_H * 2 + TRI_GAP
                row_y = node.subtree_bottom + edge_clearance
                row_height = max(item[2] for item in row)
                for child, child_width, _ in row:
                    translate(child, row_x - child.subtree_left, row_y - child.subtree_top)
                    node.subtree_left = min(node.subtree_left, child.subtree_left)
                    node.subtree_right = max(node.subtree_right, child.subtree_right)
                    node.subtree_bottom = max(node.subtree_bottom, child.subtree_bottom)
                    row_x += child_width + MIN_SPACING
                node.subtree_bottom = max(node.subtree_bottom, row_y + row_height)

        return (node.subtree_right - node.subtree_left,
                node.subtree_bottom - node.subtree_top)

    place(root, ROOT_X, ROOT_Y)

    all_nodes = []
    def collect(node):
        all_nodes.append(node)
        for child in node.children:
            collect(child)
    collect(root)

    min_x = min(node.subtree_left for node in all_nodes)
    if min_x < 4:
        shift = 4 - min_x
        for node in all_nodes:
            node.x += shift
            node.cx += shift
            node.subtree_left += shift
            node.subtree_right += shift

    max_right = max(node.subtree_right for node in all_nodes)
    max_bottom = max(node.subtree_bottom for node in all_nodes)
    return max(CANVAS_W, int(max_right + 7)), max(CANVAS_H, int(max_bottom + 8))


# --- 3. render ----------------------------------------------------------------

SHADOWED_CLASSES = {"objtype", "vartype", "reftype", "datatype"}
ITALIC_CLASSES = {"objtype", "vartype", "reftype", "datatype"}


def node_points(node):
    """Return polygon points for non-rectangular OPC UA node classes."""
    x, y, w, h = node.x, node.y, node.w, node.h
    if node.nodeclass in ("datatype", "reftype"):
        points = ((x + 10, y), (x + w - 10, y), (x + w, y + h / 2),
                  (x + w - 10, y + h), (x + 10, y + h), (x, y + h / 2))
    elif node.nodeclass == "view":
        points = ((x + 10, y), (x + w - 10, y), (x + w, y + h),
                  (x, y + h))
    else:
        return None
    return " ".join(f"{px:.0f},{py:.0f}" for px, py in points)


def render_node_svg(node, style):
    parts = []
    shadow = node.nodeclass in SHADOWED_CLASSES
    filter_attr = ' filter="url(#node-shadow)"' if shadow else ""
    parts.append(f'<g{filter_attr}>')
    fill = "url(#instance-fill)" if node.nodeclass in ("obj", "var", "method", "view") else html.escape(style["type_fill"], quote=True)
    stroke = html.escape(style["stroke"], quote=True)
    if node.nodeclass in ("var", "vartype"):
        parts.append(
            f'<rect x="{node.x:.0f}" y="{node.y:.0f}" width="{node.w:.0f}" '
            f'height="{node.h:.0f}" rx="8" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{style["stroke_width"]:g}" '
            'pointer-events="all"/>'
        )
    elif node.nodeclass == "method":
        parts.append(
            f'<ellipse cx="{node.cx:.0f}" cy="{node.cy:.0f}" '
            f'rx="{node.w / 2:.0f}" ry="{node.h / 2:.0f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{style["stroke_width"]:g}" pointer-events="all"/>'
        )
    elif (points := node_points(node)) is not None:
        parts.append(
            f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{style["stroke_width"]:g}" '
            'pointer-events="all"/>'
        )
    else:
        parts.append(
            f'<rect x="{node.x:.0f}" y="{node.y:.0f}" width="{node.w:.0f}" '
            f'height="{node.h:.0f}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{style["stroke_width"]:g}" '
            'pointer-events="all"/>'
        )
    parts.append('</g>')
    text_x = node.cx
    label_lines = []
    for line in node.label.split("\n"):
        line_parts = []
        for part in re.split(r"(\^[0-9]+)", line):
            if re.fullmatch(r"\^[0-9]+", part):
                line_parts.append(
                    f'<tspan baseline-shift="super" font-size="70%">'
                    f'{html.escape(part[1:])}</tspan>'
                )
            else:
                line_parts.append(html.escape(part))
        label_lines.append("".join(line_parts))
    line_height = FONT_SIZE * 1.2
    first_line_y = node.cy + FONT_SIZE * 0.35 - (len(label_lines) - 1) * line_height / 2
    tspans = [
        f'<tspan x="{text_x:.0f}" dy="{0 if index == 0 else line_height:.1f}">{line}</tspan>'
        for index, line in enumerate(label_lines)
    ]
    parts.append(
        f'<text x="{text_x:.0f}" y="{first_line_y:.1f}" text-anchor="middle" '
        f'font-family="{html.escape(style["font"], quote=True)}" font-size="{FONT_SIZE}" '
        f'font-style="{"italic" if node.nodeclass in ITALIC_CLASSES else "normal"}" '
        f'fill="{html.escape(style["text"], quote=True)}">{"".join(tspans)}</text>'
    )
    return parts


def reference_marker(node):
    """Return the SVG marker name for a non-inheritance reference."""
    return {
        "hasComponent": "has-component",
        "hasProperty": "has-property",
        "Organizes": "organizes",
    }.get(node.reference_type)


def reference_edge_x(child, source_x):
    """Return the node boundary where the connector must end."""
    return child.x if child.x >= source_x else child.x + child.w


def inheritance_triangle(x, y, style):
    """Render the two empty triangles used for HasSubType."""
    stroke = html.escape(style["arrow"], quote=True)
    parts = []
    for offset in (0, TRI_H + TRI_GAP):
        apex = (x, y + offset)
        bl = (x - TRI_W / 2, y + TRI_H + offset)
        br = (x + TRI_W / 2, y + TRI_H + offset)
        points = f"{apex[0]:.2f},{apex[1]:.2f} {bl[0]:.2f},{bl[1]:.2f} {br[0]:.2f},{br[1]:.2f}"
        parts.append(
            f'<polygon points="{points}" fill="white" stroke="{stroke}" stroke-width="{style["stroke_width"] * 1.5:g}"/>'
        )
    return parts


def reference_start_marker(children):
    """Return a marker placed at the source for HasTypeDefinition."""
    if any(child.reference_type == "hasTypeDefinition" for child in children):
        return "has-type-definition"
    return None


def reference_target_y(child):
    """Use the node top for type-oriented edges; others meet its center."""
    return child.y if child.reference_type in ("hasTypeDefinition", "inheritance") else child.cy


def connector_start_y(node, children):
    """Leave room for the inheritance triangle only when one is rendered."""
    if any(child.reference_type == "inheritance" for child in children):
        return node.bottom + TRI_H * 2 + TRI_GAP
    return node.bottom


def reference_groups(children):
    """Group children by reference type while preserving first-seen order."""
    groups = {}
    for child in children:
        groups.setdefault(child.reference_type, []).append(child)
    return sorted(groups.values(), key=lambda group: REFERENCE_ORDER.index(group[0].reference_type))


def reference_label_svg(x1, y1, x2, y2, reference_type, style):
    """Render the label required for non-standard reference types."""
    if reference_type != "Organizes":
        return ""
    if y1 == y2:
        x, y = (x1 + x2) / 2, y1 - 4
        anchor = "middle"
    else:
        x, y = x1 + 4, (y1 + y2) / 2
        anchor = "start"
    return (
        f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" '
        f'font-family="{html.escape(style["font"], quote=True)}" font-size="10" '
        f'fill="{html.escape(style["text"], quote=True)}">Organizes</text>'
    )


def node_anchor(node, anchor):
    """Return an anchor coordinate; omitted anchors are selected by direction."""
    if anchor == "l":
        return node.x, node.cy
    if anchor == "r":
        return node.x + node.w, node.cy
    if anchor == "t":
        return node.cx, node.y
    if anchor == "b":
        return node.cx, node.bottom
    return node.cx, node.cy


def anchor_direction(source, target):
    dx = target.cx - source.cx
    dy = target.cy - source.cy
    if abs(dx) >= abs(dy):
        return "r" if dx >= 0 else "l"
    return "b" if dy >= 0 else "t"


def anchor_side(node, anchor):
    if anchor == "l":
        return "l"
    if anchor == "r":
        return "r"
    if anchor == "t":
        return "t"
    if anchor == "b":
        return "b"
    return None


def reference_anchor_usage(root):
    """Record anchor sides occupied by hierarchy edges, grouped by reference type."""
    usage = {}

    def occupy(node, side, reference_type):
        usage.setdefault(node, {}).setdefault(side, set()).add(reference_type)

    def walk(node):
        for child in node.children:
            if child.reference_type in ("hasProperty", "hasComponent", "Organizes"):
                occupy(node, "b", child.reference_type)
                occupy(child, "l", child.reference_type)
            elif child.reference_type == "hasTypeDefinition":
                occupy(node, "b", child.reference_type)
                occupy(child, "t", child.reference_type)
            else:
                occupy(node, "b", child.reference_type)
                occupy(child, "t", child.reference_type)
            walk(child)

    walk(root)
    return usage


def choose_reference_anchor(node, preferred, reference_type, usage):
    """Choose a free anchor, allowing sharing only with the same reference type."""
    candidates = [preferred] + [side for side in "r l b t".split() if side != preferred]
    for side in candidates:
        occupied = usage.setdefault(node, {}).setdefault(side, set())
        if not occupied or occupied == {reference_type}:
            occupied.add(reference_type)
            return side
    raise ValueError(f"no available anchor for {reference_type!r} on node {node.node_id!r}")


def resolve_additional_references(root, nodes):
    usage = reference_anchor_usage(root)
    resolved = []
    for reference in root.additional_references:
        source = nodes[reference.source]
        target = nodes[reference.target]
        source_anchor = reference.source_anchor or choose_reference_anchor(
            source, anchor_direction(source, target), reference.reference_type, usage)
        target_anchor = reference.target_anchor or choose_reference_anchor(
            target, anchor_direction(target, source), reference.reference_type, usage)
        for node, side in ((source, source_anchor), (target, target_anchor)):
            occupied = usage.setdefault(node, {}).setdefault(side, set())
            if occupied and occupied != {reference.reference_type}:
                raise ValueError(
                    f"anchor [{side}] on node {node.node_id!r} is already used by "
                    f"a different reference type"
                )
            occupied.add(reference.reference_type)
        resolved.append(reference._replace(source_anchor=source_anchor, target_anchor=target_anchor))
    return resolved


def _additional_reference_svg_fallback(reference, nodes, style, routed_paths, all_nodes):
    """Fallback router used when the optional libavoid binding is unavailable."""
    source = nodes[reference.source]
    target = nodes[reference.target]
    sx, sy = node_anchor(source, reference.source_anchor)
    tx, ty = node_anchor(target, reference.target_anchor)
    margin = MIN_SPACING
    # Include endpoints as obstacles too: a same-side route must not cross the
    # target or source body before reaching its selected boundary anchor.
    obstacles = list(all_nodes)
    source_side = anchor_side(source, reference.source_anchor)
    target_side = anchor_side(target, reference.target_anchor)
    channels_y = {sy, ty}
    channels_x = {sx, tx}
    for node in obstacles:
        channels_y.update((node.y - margin, node.bottom + margin))
        channels_x.update((node.x - margin, node.x + node.w + margin))
    # The source and target are excluded from `obstacles`, but their clearance
    # channels are still required for same-side routes around either node.
    for node in (source, target):
        channels_y.update((node.y - margin, node.bottom + margin))
        channels_x.update((node.x - margin, node.x + node.w + margin))
    channels_y.update((min(node.y for node in obstacles) - margin,
                       max(node.bottom for node in obstacles) + margin))
    for path in routed_paths:
        for first, second in zip(path, path[1:]):
            if first[1] == second[1]:
                channels_y.update((first[1] - margin, first[1] + margin))
            else:
                channels_x.update((first[0] - margin, first[0] + margin))
    candidates = []
    same_side = source_side == target_side and source_side in ("l", "r", "t", "b")
    if source_side == target_side == "r":
        channels_x.add(max(source.x + source.w, target.x + target.w) + margin)
        channels_x = {x for x in channels_x if x >= max(source.x + source.w, target.x + target.w) + margin}
    elif source_side == target_side == "l":
        channels_x.add(min(source.x, target.x) - margin)
        channels_x = {x for x in channels_x if x <= min(source.x, target.x) - margin}
    elif source_side == target_side == "b":
        channels_y.add(max(source.bottom, target.bottom) + margin)
        channels_y = {y for y in channels_y if y >= max(source.bottom, target.bottom) + margin}
    elif source_side == target_side == "t":
        channels_y.add(min(source.y, target.y) - margin)
        channels_y = {y for y in channels_y if y <= min(source.y, target.y) - margin}
    if source_side == target_side == "r":
        source_channels = [source.x + source.w + margin]
        target_channels = [target.x + target.w + margin]
        for path in routed_paths:
            for first, second in zip(path, path[1:]):
                if first[0] == second[0] and first[0] > source.x + source.w:
                    source_channels.append(first[0] + margin)
                if first[0] == second[0] and first[0] > target.x + target.w:
                    target_channels.append(first[0] + margin)
        clear_y = [y for y in channels_y if y not in (sy, ty)
                   and all(y <= node.y - margin or y >= node.bottom + margin
                           for node in all_nodes)]
        for source_channel in source_channels:
            for target_channel in target_channels:
                for channel_y in clear_y:
                    candidates.append([
                        (sx, sy), (source_channel, sy), (source_channel, channel_y),
                        (target_channel, channel_y), (target_channel, ty), (tx, ty),
                    ])
    elif source_side == target_side == "l":
        source_channels = [source.x - margin]
        target_channels = [target.x - margin]
        for path in routed_paths:
            for first, second in zip(path, path[1:]):
                if first[0] == second[0] and first[0] < source.x:
                    source_channels.append(first[0] - margin)
                if first[0] == second[0] and first[0] < target.x:
                    target_channels.append(first[0] - margin)
        clear_y = [y for y in channels_y if y not in (sy, ty)
                   and all(y <= node.y - margin or y >= node.bottom + margin
                           for node in all_nodes)]
        for source_channel in source_channels:
            for target_channel in target_channels:
                for channel_y in clear_y:
                    candidates.append([
                        (sx, sy), (source_channel, sy), (source_channel, channel_y),
                        (target_channel, channel_y), (target_channel, ty), (tx, ty),
                    ])
    elif source_side == target_side == "b":
        for channel_x in channels_x:
            candidates.append([
                (sx, sy), (sx, sy + margin), (channel_x, sy + margin),
                (channel_x, ty + margin), (tx, ty + margin), (tx, ty),
            ])
    elif source_side == target_side == "t":
        for channel_x in channels_x:
            candidates.append([
                (sx, sy), (sx, sy - margin), (channel_x, sy - margin),
                (channel_x, ty - margin), (tx, ty - margin), (tx, ty),
            ])
    elif not same_side:
        for channel_y in channels_y:
            candidates.append([(sx, sy), (sx, channel_y), (tx, channel_y), (tx, ty)])
        for channel_x in channels_x:
            candidates.append([(sx, sy), (channel_x, sy), (channel_x, ty), (tx, ty)])
    else:
        for channel_x in channels_x:
            candidates.append([(sx, sy), (channel_x, sy), (channel_x, ty), (tx, ty)])
        if source_side in ("t", "b"):
            for channel_y in channels_y:
                candidates.append([(sx, sy), (sx, channel_y), (tx, channel_y), (tx, ty)])
        elif source_side in ("l", "r"):
            for channel_x in channels_x:
                for channel_y in channels_y:
                    candidates.append([
                        (sx, sy), (sx, channel_y), (channel_x, channel_y),
                        (tx, channel_y), (tx, ty),
                    ])
    candidates = [
        [point for index, point in enumerate(candidate)
         if index == 0 or point != candidate[index - 1]]
        for candidate in candidates
    ]
    if not candidates:
        candidates = [[(sx, sy), (sx + margin, sy), (tx + margin, ty), (tx, ty)]]
    candidates = [
        candidate for candidate in candidates
        if len(candidate) > 1 and all(a != b for a, b in zip(candidate, candidate[1:]))
    ]

    def blocked(a, b, node):
        if a[0] == b[0]:
            return node.x <= a[0] <= node.x + node.w and max(min(a[1], b[1]), node.y) <= min(max(a[1], b[1]), node.bottom)
        if a[1] == b[1]:
            return node.y <= a[1] <= node.bottom and max(min(a[0], b[0]), node.x) <= min(max(a[0], b[0]), node.x + node.w)
        return True

    def parallel_conflicts(a, b, path):
        """Count prior collinear segments that violate MIN_SPACING."""
        if a == b:
            return 0
        conflicts = 0
        for c, d in zip(path, path[1:]):
            if c[1] == d[1] and a[1] == b[1]:
                if abs(a[1] - c[1]) < margin and max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])):
                    conflicts += 1
            elif c[0] == d[0] and a[0] == b[0]:
                if abs(a[0] - c[0]) < margin and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])):
                    conflicts += 1
        return conflicts

    def crossings(a, b, path):
        """Count strict perpendicular crossings with a prior route."""
        if a == b:
            return 0
        count = 0
        horizontal = a[1] == b[1]
        for c, d in zip(path, path[1:]):
            other_horizontal = c[1] == d[1]
            if horizontal == other_horizontal:
                continue
            horizontal_segment = (a, b) if horizontal else (c, d)
            vertical_segment = (c, d) if horizontal else (a, b)
            hx1, hx2 = sorted((horizontal_segment[0][0], horizontal_segment[1][0]))
            vy1, vy2 = sorted((vertical_segment[0][1], vertical_segment[1][1]))
            x, y = vertical_segment[0][0], horizontal_segment[0][1]
            if hx1 < x < hx2 and vy1 < y < vy2:
                count += 1
        return count

    def score(candidate):
        blocked_count = 0
        for segment_index, (a, b) in enumerate(zip(candidate, candidate[1:])):
            for node in obstacles:
                endpoint_segment = (
                    (node is source and segment_index == 0)
                    or (node is target and segment_index == len(candidate) - 2)
                )
                if not endpoint_segment and blocked(a, b, node):
                    blocked_count += 1
        length = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(candidate, candidate[1:]))
        edge_conflicts = sum(
            parallel_conflicts(a, b, prior)
            for a, b in zip(candidate, candidate[1:])
            for prior in routed_paths
        )
        crossing_count = sum(
            crossings(a, b, prior)
            for a, b in zip(candidate, candidate[1:])
            for prior in routed_paths
        )
        bends = sum(
            (a[0] != b[0] and b[1] != c[1]) or (a[1] != b[1] and b[0] != c[0])
            for a, b, c in zip(candidate, candidate[1:], candidate[2:])
        )
        # Crossings may be unavoidable for a fixed node order. Prefer fewer
        # crossings before optimizing bends and length, while keeping parallel
        # clearance as the stronger constraint.
        return (blocked_count * 1_000_000 + edge_conflicts * 100_000
                + crossing_count * 10_000 + bends * 100 + length)

    path = min(candidates, key=score)
    points = " ".join(f"{x:.0f},{y:.0f}" for x, y in path)
    label_x, label_y = path[len(path) // 2]
    routed_paths.append(path)
    return [
        f'<polyline points="{points}" fill="none" stroke="{html.escape(style["arrow"], quote=True)}" '
        f'stroke-width="{style["stroke_width"]:g}" marker-end="url(#additional-reference)"/>',
        f'<text x="{label_x:.0f}" y="{label_y - 4:.0f}" text-anchor="middle" '
        f'font-family="{html.escape(style["font"], quote=True)}" font-size="10" '
        f'fill="{html.escape(style["text"], quote=True)}">{html.escape(reference.reference_type)}</text>',
    ]


def _libavoid_direction(anchor):
    """Return pybind11/libavoid visibility flags for a selected node side."""
    return {
        "l": _adaptagrams.CONN_DIR_LEFT,
        "r": _adaptagrams.CONN_DIR_RIGHT,
        "t": _adaptagrams.CONN_DIR_UP,
        "b": _adaptagrams.CONN_DIR_DOWN,
    }[anchor]


def route_additional_references_libavoid(references, nodes, all_nodes, fixed_paths):
    """Route all additional references in one libavoid transaction."""
    if _adaptagrams is None or not references:
        return None

    rectangles = [
        _adaptagrams.Rectangle(node.x, node.y, node.w, node.h)
        for node in all_nodes
    ]
    connections = []
    node_indices = {node: index for index, node in enumerate(all_nodes)}
    for reference in references:
        source = nodes[reference.source]
        target = nodes[reference.target]
        sx, sy = node_anchor(source, reference.source_anchor)
        tx, ty = node_anchor(target, reference.target_anchor)
        connections.append(_adaptagrams.Connection(
            node_indices[source], node_indices[target],
            sx, sy, tx, ty,
            _libavoid_direction(reference.source_anchor),
            _libavoid_direction(reference.target_anchor),
        ))
    native_routes = _adaptagrams.route(
        rectangles, connections,
        fixed_paths,
        shape_buffer_distance=MIN_SPACING,
        ideal_nudging_distance=MIN_SPACING,
        segment_penalty=10.0,
        crossing_penalty=10000.0,
    )
    routes = dict(zip(references, native_routes))
    return routes


def additional_reference_svg(reference, nodes, style, path):
    """Render a route produced by libavoid."""
    # libavoid pins are offset inside shapes to route around the buffered
    # obstacle. Render the visible endpoints on the node boundaries instead.
    source_boundary = node_anchor(nodes[reference.source], reference.source_anchor)
    target_boundary = node_anchor(nodes[reference.target], reference.target_anchor)
    rendered_path = list(path)

    def add_orthogonal_endpoint(points, node, boundary, side, at_start):
        points = list(points)

        def inside(point):
            return (node.x <= point[0] <= node.x + node.w
                    and node.y <= point[1] <= node.bottom)

        # ShapeConnectionPin endpoints are intentionally inside the node. Do
        # not render those points: the visible route must leave the boundary
        # in the selected outward direction.
        if at_start:
            while len(points) > 1 and inside(points[0]):
                points.pop(0)
        else:
            while len(points) > 1 and inside(points[-1]):
                points.pop()
        native = points[0] if at_start else points[-1]
        if side == "r":
            outward = (boundary[0] + MIN_SPACING, boundary[1])
        elif side == "l":
            outward = (boundary[0] - MIN_SPACING, boundary[1])
        elif side == "b":
            outward = (boundary[0], boundary[1] + MIN_SPACING)
        else:
            outward = (boundary[0], boundary[1] - MIN_SPACING)
        bridge = ((outward[0], native[1]) if side in ("l", "r")
                  else (native[0], outward[1]))
        if at_start:
            return [boundary, outward, bridge] + points
        return points + [bridge, outward, boundary]

    rendered_path = add_orthogonal_endpoint(
        rendered_path, nodes[reference.source], source_boundary,
        reference.source_anchor, True
    )
    rendered_path = add_orthogonal_endpoint(
        rendered_path, nodes[reference.target], target_boundary,
        reference.target_anchor, False
    )
    simplified = [rendered_path[0]]
    for point in rendered_path[1:]:
        if point == simplified[-1]:
            continue
        if (len(simplified) >= 2
                and ((simplified[-2][0] == simplified[-1][0] == point[0])
                     or (simplified[-2][1] == simplified[-1][1] == point[1]))):
            simplified[-1] = point
        else:
            simplified.append(point)
    rendered_path = simplified
    points = " ".join(f"{x:.0f},{y:.0f}" for x, y in rendered_path)
    segments = list(zip(rendered_path, rendered_path[1:]))
    label_segment = max(
        segments,
        key=lambda segment: abs(segment[1][0] - segment[0][0])
        + abs(segment[1][1] - segment[0][1]),
    )
    first, second = label_segment
    label_width_estimate = len(reference.reference_type) * 10 * 0.6
    if first[1] == second[1]:
        label_x = (first[0] + second[0]) / 2
        label_y = first[1] - 4
    else:
        label_x = min(first[0], second[0]) + 4
        label_y = (first[1] + second[1]) / 2
    label_x = max(label_width_estimate / 2 + 4,
                  min(CANVAS_W - label_width_estimate / 2 - 4, label_x))
    label_y = max(FONT_SIZE, min(CANVAS_H - 2, label_y))
    symmetric = reference.reference_type.lower() == "associatedwith"
    marker = "associated-with" if symmetric else "additional-reference"
    marker_start = f' marker-start="url(#{marker})"' if symmetric else ""
    return [
        f'<polyline points="{points}" fill="none" stroke="{html.escape(style["arrow"], quote=True)}" '
        f'stroke-width="{style["stroke_width"]:g}"{marker_start} marker-end="url(#{marker})"/>',
        f'<text x="{label_x:.0f}" y="{label_y - 4:.0f}" text-anchor="middle" '
        f'font-family="{html.escape(style["font"], quote=True)}" font-size="10" '
        f'fill="{html.escape(style["text"], quote=True)}">{html.escape(reference.reference_type)}</text>',
    ]


def fixed_connector_paths(parts):
    """Extract existing hierarchy line segments for libavoid's fixed routes."""
    paths = []
    pattern = re.compile(
        r'<line[^>]*x1="([0-9.+-]+)"[^>]*y1="([0-9.+-]+)"[^>]*'
        r'x2="([0-9.+-]+)"[^>]*y2="([0-9.+-]+)"'
    )
    for part in parts:
        for match in pattern.finditer(part):
            x1, y1, x2, y2 = (float(value) for value in match.groups())
            paths.append([(x1, y1), (x2, y2)])
    return paths


def reference_anchors(node, groups):
    """Place one trunk anchor at each separation of the source bottom edge."""
    count = len(groups)
    return [node.x + (index + 1) * node.w / (count + 1)
            for index in range(count)]


def render_connectors_svg(node, style):
    """Draw the merged trunk + stubs from `node` down to its children."""
    parts = []
    if not node.children:
        return parts

    groups = reference_groups(node.children)
    for children, trunk_x in zip(groups, reference_anchors(node, groups)):
        start_y = connector_start_y(node, children)
        start_marker = reference_start_marker(children)
        start_marker_attr = f' marker-start="url(#{start_marker})"' if start_marker else ""
        if children[0].reference_type == "inheritance":
            approach_ys = {child: child.y - MIN_SPACING for child in children}
            trunk_end_y = max(approach_ys.values())
            parts.append(
                f'<line x1="{trunk_x:.0f}" y1="{start_y:.2f}" '
                f'x2="{trunk_x:.0f}" y2="{trunk_end_y:.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                f'{start_marker_attr}/>'
            )
            for child in children:
                approach_y = approach_ys[child]
                parts.append(
                    f'<line x1="{trunk_x:.0f}" y1="{approach_y:.0f}" '
                    f'x2="{child.cx:.0f}" y2="{approach_y:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                )
                parts.append(
                    f'<line x1="{child.cx:.0f}" y1="{approach_y:.0f}" '
                    f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                )
            continue

        last_cy = max(reference_target_y(child) for child in children)
        parts.append(
            f'<line x1="{trunk_x:.0f}" y1="{start_y:.2f}" '
            f'x2="{trunk_x:.0f}" y2="{last_cy:.0f}" '
            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
            f'{start_marker_attr}/>'
        )
        if children[0].reference_type == "inheritance":
            approach_y = min(child.y for child in children) - MIN_SPACING
            parts.append(
                f'<line x1="{min(trunk_x, min(child.cx for child in children)):.0f}" '
                f'y1="{approach_y:.0f}" x2="{max(trunk_x, max(child.cx for child in children)):.0f}" '
                f'y2="{approach_y:.0f}" stroke="{html.escape(style["arrow"], quote=True)}" '
                'stroke-width="1"/>'
            )
            for child in children:
                parts.append(
                    f'<line x1="{child.cx:.0f}" y1="{approach_y:.0f}" '
                    f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                )
            continue
        for child in children:
            marker = reference_marker(child)
            marker_attr = f' marker-end="url(#{marker})"' if marker else ""
            target_y = reference_target_y(child)
            parts.append(
                f'<line x1="{trunk_x:.0f}" y1="{target_y:.0f}" '
                f'x2="{reference_edge_x(child, trunk_x):.0f}" '
                f'y2="{target_y:.0f}" stroke="{html.escape(style["arrow"], quote=True)}" '
                f'stroke-width="1"{marker_attr}/>'
            )
            parts.append(reference_label_svg(
                trunk_x, target_y,
                reference_edge_x(child, trunk_x),
                target_y, child.reference_type, style
            ))

    if any(child.reference_type == "inheritance" for child in node.children):
        parts.extend(inheritance_triangle(trunk_x, node.bottom + TRI_GAP, style))

    return parts


def render_root_connectors_svg(root, style):
    """Root's children are spread horizontally: one shared horizontal bus at
    root.bottom + GAP_Y_ROOT/2, with a stub down from root and a stub down
    into each child, plus one triangle at root's own bottom edge."""
    if not root.children:
        return []

    parts = []
    bus_y = 83
    source_y = connector_start_y(root, root.children)
    branch_groups = {}
    for child in root.children:
        branch_groups.setdefault(child.branch_group, []).append(child)
    if len(branch_groups) > 1:
        root_reference_groups = reference_groups(root.children)
        root_anchors = reference_anchors(root, root_reference_groups)
        routed_groups = []
        for children in root_reference_groups:
            first = children[0]
            direction = 1 if first.cx >= root.cx else -1
            if first.reference_type == "inheritance":
                trunk_x = root_anchors[len(routed_groups)]
            else:
                trunk_x = first.x - 20 if direction > 0 else first.x + first.w + 20
            routed_groups.append((children, trunk_x))

        property_routes = [(group, trunk_x, root_anchors[index])
                           for index, (group, trunk_x) in enumerate(routed_groups)
                           if group[0].reference_type == "hasProperty"]
        structural_routes = [(group, trunk_x, root_anchors[index])
                             for index, (group, trunk_x) in enumerate(routed_groups)
                             if group[0].reference_type != "hasProperty"]
        for children, _, route_x in property_routes:
            parts.append(
                f'<line x1="{route_x:.0f}" y1="{source_y:.2f}" '
                f'x2="{route_x:.0f}" y2="{max(child.cy for child in children):.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
            )
            for child in children:
                marker = reference_marker(child)
                marker_attr = f' marker-end="url(#{marker})"' if marker else ""
                edge_x = reference_edge_x(child, route_x)
                parts.append(
                    f'<line x1="{route_x:.0f}" y1="{child.cy:.0f}" '
                    f'x2="{edge_x:.0f}" y2="{child.cy:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                    f'{marker_attr}/>'
                )
        if structural_routes:
            property_bottom = max(
                (child.bottom for children, _, _ in property_routes for child in children),
                default=root.bottom,
            )
            branch_bus_y = property_bottom + 20
            for children, trunk_x, route_x in structural_routes:
                if children[0].reference_type == "hasTypeDefinition":
                    approach_ys = {child: child.y - MIN_SPACING for child in children}
                    branch_bus_y = max(approach_ys.values())
                    parts.append(
                        f'<line x1="{route_x:.0f}" y1="{source_y:.2f}" '
                        f'x2="{route_x:.0f}" y2="{branch_bus_y:.0f}" '
                        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                        ' marker-start="url(#has-type-definition)"/>'
                    )
                    for child in children:
                        approach_y = approach_ys[child]
                        parts.append(
                            f'<line x1="{route_x:.0f}" y1="{approach_y:.0f}" '
                            f'x2="{child.cx:.0f}" y2="{approach_y:.0f}" '
                            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                        )
                        parts.append(
                            f'<line x1="{child.cx:.0f}" y1="{approach_y:.0f}" '
                            f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
                            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                        )
                    continue
                elif children[0].reference_type == "inheritance":
                    approach_ys = {child: child.y - MIN_SPACING for child in children}
                    branch_bus_y = max(approach_ys.values())
                    parts.append(
                        f'<line x1="{route_x:.0f}" y1="{source_y:.2f}" '
                        f'x2="{route_x:.0f}" y2="{branch_bus_y:.0f}" '
                        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                    )
                    for child in children:
                        approach_y = approach_ys[child]
                        parts.append(
                            f'<line x1="{route_x:.0f}" y1="{approach_y:.0f}" '
                            f'x2="{child.cx:.0f}" y2="{approach_y:.0f}" '
                            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                        )
                        parts.append(
                            f'<line x1="{child.cx:.0f}" y1="{approach_y:.0f}" '
                            f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
                            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                        )
                    continue
                else:
                    parts.append(
             f'<line x1="{route_x:.0f}" y1="{source_y:.2f}" '
                        f'x2="{route_x:.0f}" y2="{branch_bus_y:.0f}" '
                        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                    )
                    route_start_y = branch_bus_y
                parts.append(
                    f'<line x1="{route_x:.0f}" y1="{route_start_y:.0f}" '
                    f'x2="{trunk_x:.0f}" y2="{route_start_y:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                )
                parts.append(
                    f'<line x1="{trunk_x:.0f}" y1="{route_start_y:.0f}" '
                    f'x2="{trunk_x:.0f}" y2="{max(reference_target_y(child) for child in children):.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
                )
                for child in children:
                    marker = reference_marker(child)
                    marker_attr = f' marker-end="url(#{marker})"' if marker else ""
                    target_y = reference_target_y(child)
                    edge_x = reference_edge_x(child, trunk_x)
                    parts.append(
                        f'<line x1="{trunk_x:.0f}" y1="{target_y:.0f}" '
                        f'x2="{edge_x:.0f}" y2="{target_y:.0f}" '
                        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                        f'{marker_attr}/>'
                    )
        if any(child.reference_type == "inheritance" for child in root.children):
            parts.extend(inheritance_triangle(root.cx, root.bottom + TRI_GAP, style))
        return parts

    reference_type_groups = reference_groups(root.children)
    if (len(reference_type_groups) == 1
            and reference_type_groups[0][0].reference_type == "Organizes"):
        children = reference_type_groups[0]
        trunk_x = reference_anchors(root, reference_type_groups)[0]
        parts.append(
            f'<line x1="{trunk_x:.0f}" y1="{source_y:.2f}" '
            f'x2="{trunk_x:.0f}" y2="{max(child.cy for child in children):.0f}" '
            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
        )
        for child in children:
            marker = reference_marker(child)
            marker_attr = f' marker-end="url(#{marker})"' if marker else ""
            parts.append(
                f'<line x1="{trunk_x:.0f}" y1="{child.cy:.0f}" '
                f'x2="{child.x:.0f}" y2="{child.cy:.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                f'{marker_attr}/>'
            )
            parts.append(reference_label_svg(
                trunk_x, child.cy, child.x, child.cy,
                child.reference_type, style
            ))
        return parts
    if len(reference_type_groups) > 1 and len({child.branch_group for child in root.children}) == 1:
        anchors = reference_anchors(root, reference_type_groups)
        for index, children in enumerate(reference_type_groups):
            current_bus_y = bus_y + index * 12
            anchor = anchors[index]
            start_marker = reference_start_marker(children)
            start_marker_attr = f' marker-start="url(#{start_marker})"' if start_marker else ""
            parts.append(
                f'<line x1="{anchor:.0f}" y1="{source_y:.2f}" '
                f'x2="{anchor:.0f}" y2="{current_bus_y:.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                f'{start_marker_attr}/>'
            )
            xs = [child.cx for child in children]
            parts.append(
                f'<line x1="{min(xs):.0f}" y1="{current_bus_y:.0f}" '
                f'x2="{max(xs):.0f}" y2="{current_bus_y:.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
            )
            for child in children:
                marker = reference_marker(child)
                marker_attr = f' marker-end="url(#{marker})"' if marker else ""
                parts.append(
                    f'<line x1="{child.cx:.0f}" y1="{current_bus_y:.0f}" '
                    f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                    f'{marker_attr}/>'
                )
        if any(child.reference_type == "inheritance" for child in root.children):
            parts.extend(inheritance_triangle(root.cx, root.bottom + TRI_GAP, style))
        return parts

    # stub from root down to the bus
    start_marker = reference_start_marker(root.children)
    start_marker_attr = f' marker-start="url(#{start_marker})"' if start_marker else ""
    parts.append(
        f'<line x1="{root.cx:.0f}" y1="{source_y:.2f}" '
        f'x2="{root.cx:.0f}" y2="{bus_y:.0f}" '
        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
        f'{start_marker_attr}/>'
    )
    groups = {}
    for child in root.children:
        groups.setdefault(child.branch_group, []).append(child)
    grouped_columns = len(groups) > 1
    group_trunks = []
    if grouped_columns:
        for column in groups.values():
            ref_groups = reference_groups(column)
            offsets = [0] if len(ref_groups) == 1 else [
                (index - (len(ref_groups) - 1) / 2) * 12
                for index in range(len(ref_groups))
            ]
            for children, offset in zip(ref_groups, offsets):
                child = children[0]
                direction = 1 if child.cx >= root.cx else -1
                trunk_x = child.x - 20 if direction > 0 else child.x + child.w + 20
                group_trunks.append((trunk_x + offset, children))
    else:
        group_trunks = [(child.cx, [child]) for child in root.children]

    xs = [trunk_x for trunk_x, _ in group_trunks] if grouped_columns else [c.cx for c in root.children]
    parts.append(
        f'<line x1="{min(xs):.0f}" y1="{bus_y:.0f}" '
        f'x2="{max(xs):.0f}" y2="{bus_y:.0f}" '
        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
    )
    for trunk_x, children in group_trunks:
        if grouped_columns:
            parts.append(
                f'<line x1="{trunk_x:.0f}" y1="{bus_y:.0f}" '
                f'x2="{trunk_x:.0f}" y2="{children[-1].cy:.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
            )
            direction = 1 if children[0].cx >= root.cx else -1
            for child in children:
                marker = reference_marker(child)
                marker_attr = f' marker-end="url(#{marker})"' if marker else ""
                edge_x = reference_edge_x(child, trunk_x)
                parts.append(
                    f'<line x1="{trunk_x:.0f}" y1="{child.cy:.0f}" '
                    f'x2="{edge_x:.0f}" y2="{child.cy:.0f}" '
                    f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                    f'{marker_attr}/>'
                )
        else:
            child = children[0]
            marker = reference_marker(child)
            marker_attr = f' marker-end="url(#{marker})"' if marker else ""
            parts.append(
                f'<line x1="{child.cx:.0f}" y1="{bus_y:.0f}" '
                f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
                f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
                f'{marker_attr}/>'
            )

    if any(child.reference_type == "inheritance" for child in root.children):
        parts.extend(inheritance_triangle(root.cx, root.bottom + TRI_GAP, style))

    return parts


def render_defs(style):
    parts = ["<defs>"]
    parts.append(
        '<filter id="node-shadow" x="-20%" y="-20%" width="150%" height="150%">'
        '<feDropShadow dx="4" dy="5" stdDeviation="1.5" flood-color="#000000" '
        'flood-opacity="0.5"/></filter>'
    )
    parts.append(
        '<linearGradient id="instance-fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{html.escape(style["instance_fill_start"], quote=True)}"/>'
        f'<stop offset="100%" stop-color="{html.escape(style["instance_fill_end"], quote=True)}"/>'
        '</linearGradient>'
    )
    parts.extend((
        '<marker id="has-type-definition" viewBox="0 0 20.78 12" markerWidth="20.78" '
        'markerHeight="12" refX="20.78" refY="6" orient="auto-start-reverse" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L10.39,6 L0,12 Z M10.39,0 L20.78,6 L10.39,12 Z" '
        'fill="context-stroke"/></marker>',
        '<marker id="has-component" viewBox="0 0 6 12" markerWidth="6" '
        'markerHeight="12" refX="6" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
        f'<path d="M{REFERENCE_MARKER_GAP * 0.75:.1f},0 L{REFERENCE_MARKER_GAP * 0.75:.1f},12" '
        'fill="none" stroke="context-stroke" stroke-width="1"/></marker>',
        '<marker id="has-property" viewBox="0 0 10.5 12" markerWidth="10.5" '
        'markerHeight="12" refX="10.5" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
        f'<path d="M{REFERENCE_MARKER_GAP * 0.75 - 1.5:.1f},0 L{REFERENCE_MARKER_GAP * 0.75 - 1.5:.1f},12 '
        f'M{REFERENCE_MARKER_GAP * 0.75 + 1.5:.1f},0 L{REFERENCE_MARKER_GAP * 0.75 + 1.5:.1f},12" '
        'fill="none" stroke="context-stroke" '
        'stroke-width="1"/></marker>',
        '<marker id="organizes" viewBox="0 0 15 12" markerWidth="15" '
        'markerHeight="12" refX="15" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L15,6 L0,12" fill="none" stroke="context-stroke" '
        'stroke-width="1"/></marker>',
        '<marker id="additional-reference" viewBox="0 0 15 12" markerWidth="15" '
        'markerHeight="12" refX="15" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L15,6 L0,12" fill="none" stroke="context-stroke" '
        'stroke-width="1"/></marker>',
        '<marker id="associated-with" viewBox="0 0 10.39 12" markerWidth="10.39" '
        'markerHeight="12" refX="10.39" refY="6" orient="auto-start-reverse" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L10.39,6 L0,12" fill="context-stroke" stroke="context-stroke" '
        'stroke-width="1"/></marker>',
    ))
    parts.append("</defs>")
    return "".join(parts)


def to_svg(root):
    W, H = layout(root)

    nodes = []
    connectors = []
    nodes_by_id = {}
    all_nodes = []

    def walk(node, is_root=False):
        nodes.extend(render_node_svg(node, root.style))
        all_nodes.append(node)
        if node.node_id:
            nodes_by_id[node.node_id] = node
        if is_root:
            connectors.extend(render_root_connectors_svg(node, root.style))
        else:
            connectors.extend(render_connectors_svg(node, root.style))
        for child in node.children:
            walk(child)

    walk(root, is_root=True)
    references = resolve_additional_references(root, nodes_by_id)
    if references and _adaptagrams is None:
        print("libavoid unavailable; skipping additional references", file=sys.stderr)
    elif references:
        try:
            libavoid_routes = route_additional_references_libavoid(
                references, nodes_by_id, all_nodes,
                fixed_connector_paths(connectors)
            )
        except Exception as exc:
            print(f"libavoid routing failed; skipping additional references: {exc}", file=sys.stderr)
        else:
            for reference in references:
                connectors.extend(additional_reference_svg(
                    reference, nodes_by_id, root.style, libavoid_routes[reference]
                ))

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}px" height="{H}px" '
        f'viewBox="-0.5 -0.5 {W} {H}">\n'
        + render_defs(root.style) + '\n'
        + '<g>\n'
        + "\n".join(nodes + connectors) +
        '\n</g>\n</svg>\n'
    )
    svg = svg.replace('stroke-width="1.5"',
                      f'stroke-width="{root.style["stroke_width"] * 1.5:g}"')
    svg = svg.replace('stroke-width="1"',
                      f'stroke-width="{root.style["stroke_width"]:g}"')
    return svg


# --- CLI ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("infile", help="input type-system file with '*'-depth nodes")
    ap.add_argument("-o", "--outfile", help="output SVG path (default: <infile>.svg)")
    args = ap.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        text = f.read()

    root = parse(text)
    svg = to_svg(root)

    outfile = args.outfile
    if not outfile:
        import os
        base, _ = os.path.splitext(args.infile)
        outfile = base + ".svg"

    with open(outfile, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"wrote {outfile}", file=sys.stderr)


if __name__ == "__main__":
    main()
