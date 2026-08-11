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

Node shadows can be disabled with `skinparam shadowing false`,
`skinparam nodeShadowing false`, or `Shadowing false` inside a
`skinparam node { ... }` block.

Depth = number of leading '*' characters. The overview layout places the two
top-level branches below the root and sends each branch's leaves outward,
matching the reference OPC UA diagram.

Usage:
    python3 tree2svg.py input.puml -o output.svg
    python3 tree2svg.py input.puml -o output.svg --no-triangles
"""

import argparse
import html
import re
import sys


# --- geometry / style constants --------------------------------------------

FONT_SIZE = 12
FONT_FAMILY = "Helvetica"
BOX_W = 230             # The reference uses the same width for every node.
BOX_H = 40
ROOT_X, ROOT_Y = 298, 4
PARENT_Y = 122
LEAF_Y = 202
ROW_GAP = 20            # 40px node + 20px between leaf rows
PARENT_GAP = 42
CANVAS_W, CANVAS_H = 837, 550
NODE_SHADOW_DEFAULT = True

FILL = "#e6ecf7"
STROKE = "#4a6fa5"
TEXT_COLOR = "#000000"
TRI_W, TRI_H = 7, 7     # inheritance triangle size in the reference export


# --- 1. parse ----------------------------------------------------------------

REFERENCE_TYPES = {
    "inheritance": "inheritance",
    "hastypedefinition": "hasTypeDefinition",
    "hascomponent": "hasComponent",
    "hasproperty": "hasProperty",
}
NODE_CLASSES = {"obj", "objtype", "var", "vartype", "method", "reftype", "datatype", "view"}


class Node:
    __slots__ = ("label", "nodeclass", "reference_type", "children", "x", "y", "w", "h", "cx", "cy",
                 "bottom", "subtree_bottom", "subtree_left", "subtree_right",
                 "node_shadow", "style")

    def __init__(self, label, nodeclass="objtype", reference_type=None):
        self.label = label
        self.nodeclass = nodeclass
        self.reference_type = reference_type
        self.children = []
        self.x = self.y = self.w = self.h = 0.0
        self.cx = self.cy = self.bottom = 0.0
        self.subtree_bottom = self.subtree_left = self.subtree_right = 0.0
        self.node_shadow = NODE_SHADOW_DEFAULT
        self.style = {
            "fill": FILL,
            "stroke": STROKE,
            "text": TEXT_COLOR,
            "font": FONT_FAMILY,
            "arrow": STROKE,
        }


def parse(text):
    """Parse '*'-depth WBS syntax into a Node tree. Returns the root Node."""
    stack = []  # (depth, node)
    root = None
    node_shadow = NODE_SHADOW_DEFAULT
    style = {
        "fill": FILL,
        "stroke": STROKE,
        "text": TEXT_COLOR,
        "font": FONT_FAMILY,
        "arrow": STROKE,
    }
    in_node_skinparam = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
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
        setting = re.match(r"^(?:skinparam\s+)?([A-Za-z]+)\s+(.+)$", stripped)
        if setting:
            key, value = setting.group(1).lower(), setting.group(2).strip()
            node_setting = in_node_skinparam or key.startswith("node")
            if key.startswith("node"):
                key = key[4:]
            if node_setting and key in ("backgroundcolor", "fill"):
                style["fill"] = value
                continue
            if node_setting and key in ("bordercolor", "stroke"):
                style["stroke"] = value
                continue
            if node_setting and key in ("fontcolor", "textcolor"):
                style["text"] = value
                continue
            if node_setting and key in ("fontname", "fontfamily"):
                style["font"] = value
                continue
            if key in ("arrowcolor", "linecolor"):
                style["arrow"] = value
                continue
        shadow_match = re.match(
            r"^skinparam\s+(?:node\s+)?shadow(?:ing)?\s+(true|false)$",
            stripped,
            re.IGNORECASE,
        )
        if not shadow_match:
            shadow_match = re.match(
                r"^skinparam\s+nodeShadow(?:ing)?\s+(true|false)$",
                stripped,
                re.IGNORECASE,
            )
        if shadow_match or (in_node_skinparam and re.match(
                r"^shadow(?:ing)?\s+(true|false)$", stripped, re.IGNORECASE)):
            node_shadow = (shadow_match or re.match(
                r"^shadow(?:ing)?\s+(true|false)$", stripped, re.IGNORECASE
            )).group(1).lower() == "true"
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
        label_match = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', label_text)
        if not label_match:
            raise ValueError(f"node label must be quoted near: {stripped!r}")
        label = label_match.group(1).replace(r'\"', '"').replace(r'\\', '\\')
        node = Node(label, nodeclass, explicit_reference)
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
        if node.reference_type is None:
            node.reference_type = infer_reference_type(parent.nodeclass, node.nodeclass)
        parent.children.append(node)
        stack.append((depth, node))
    if root is None:
        raise ValueError("no root node found (expected a line starting with a single '*')")
    root.node_shadow = node_shadow
    root.style = style
    return root


def infer_reference_type(source_class, destination_class):
    """Infer the common OPC UA reference for a parent-child edge."""
    if source_class == "obj" and destination_class == "objtype":
        return "hasTypeDefinition"
    if source_class == "obj" and destination_class == "obj":
        return "hasComponent"
    if source_class == "obj" and destination_class in ("var", "vartype"):
        return "hasProperty"
    if source_class in ("obj", "objtype") and destination_class in ("var", "vartype"):
        return "hasProperty"
    return "inheritance"


# --- 2. layout ----------------------------------------------------------------

def set_box(node, x, y):
    node.w = BOX_W
    node.h = BOX_H
    node.x, node.y = x, y
    node.cx, node.cy = x + BOX_W / 2, y + BOX_H / 2
    node.bottom = y + BOX_H
    node.subtree_left = x
    node.subtree_right = x + BOX_W
    node.subtree_bottom = node.bottom


def layout(root):
    """Lay out a rooted tree with outward-growing, vertically stacked branches.

    The two-branch case retains the reference OPC UA coordinates. For deeper
    trees, each descendant is placed one column farther outward and its
    siblings are allocated enough vertical space for their complete subtree.
    """
    set_box(root, ROOT_X, ROOT_Y)

    def place_branch(node, x, y, direction):
        """Place node and recursively place children in the outward column."""
        set_box(node, x, y)
        node.subtree_left = node.x
        node.subtree_right = node.x + node.w
        node.subtree_bottom = node.bottom
        if not node.children:
            return

        child_x = node.x - 164 if direction < 0 else node.x + 160
        child_y = node.bottom + 40
        for child in node.children:
            place_branch(child, child_x, child_y, direction)
            node.subtree_left = min(node.subtree_left, child.subtree_left)
            node.subtree_right = max(node.subtree_right, child.subtree_right)
            node.subtree_bottom = max(node.subtree_bottom, child.subtree_bottom)
            child_y = child.subtree_bottom + ROW_GAP

    if len(root.children) == 2:
        # These offsets produce x=168/440 and preserve the reference image.
        branch_positions = ((ROOT_X - 130, -1), (ROOT_X + 142, 1))
    else:
        # A right-facing descendant reaches 275px beyond its parent's center
        # at depth one. Increase the column spacing for every further level so
        # the next branch's vertical trunk cannot cross that node.
        def depth(node):
            return 0 if not node.children else 1 + max(depth(c) for c in node.children)

        right_depth = max((depth(child) for child in root.children), default=0)
        spacing = max(BOX_W + PARENT_GAP, 120 + right_depth * 160)
        # Keep arbitrary root fan-outs centered around the root.
        first_center = root.cx - (len(root.children) - 1) * spacing / 2
        branch_positions = [
            (first_center + i * spacing - BOX_W / 2,
             -1 if first_center + i * spacing < root.cx else 1)
            for i in range(len(root.children))
        ]

    for child, (x, direction) in zip(root.children, branch_positions):
        place_branch(child, x, PARENT_Y, direction)
        root.subtree_left = min(root.subtree_left, child.subtree_left)
        root.subtree_right = max(root.subtree_right, child.subtree_right)
        root.subtree_bottom = max(root.subtree_bottom, child.subtree_bottom)

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


def render_node_svg(node, style, shadow=True):
    parts = []
    shadow = shadow and node.nodeclass in SHADOWED_CLASSES
    filter_attr = ' filter="url(#node-shadow)"' if shadow else ""
    parts.append(f'<g{filter_attr}>')
    fill = html.escape(style["fill"], quote=True)
    stroke = html.escape(style["stroke"], quote=True)
    if node.nodeclass in ("var", "vartype"):
        parts.append(
            f'<rect x="{node.x:.0f}" y="{node.y:.0f}" width="{node.w:.0f}" '
            f'height="{node.h:.0f}" rx="8" fill="{fill}" stroke="{stroke}" '
            'pointer-events="all"/>'
        )
    elif node.nodeclass == "method":
        parts.append(
            f'<ellipse cx="{node.cx:.0f}" cy="{node.cy:.0f}" '
            f'rx="{node.w / 2:.0f}" ry="{node.h / 2:.0f}" fill="{fill}" '
            f'stroke="{stroke}" pointer-events="all"/>'
        )
    elif (points := node_points(node)) is not None:
        parts.append(
            f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" '
            'pointer-events="all"/>'
        )
    else:
        parts.append(
            f'<rect x="{node.x:.0f}" y="{node.y:.0f}" width="{node.w:.0f}" '
            f'height="{node.h:.0f}" fill="{fill}" stroke="{stroke}" '
            'pointer-events="all"/>'
        )
    parts.append('</g>')
    text_x = node.cx
    text_y = node.cy + FONT_SIZE * 0.35
    label = html.escape(node.label)
    parts.append(
        f'<text x="{text_x:.0f}" y="{text_y:.0f}" text-anchor="middle" '
        f'font-family="{html.escape(style["font"], quote=True)}" font-size="{FONT_SIZE}" '
        f'font-style="{"italic" if node.nodeclass in ITALIC_CLASSES else "normal"}" '
        f'fill="{html.escape(style["text"], quote=True)}">{label}</text>'
    )
    return parts


def reference_marker(node):
    """Return the SVG marker name for a non-inheritance reference."""
    return {
        "hasTypeDefinition": "has-type-definition",
        "hasComponent": "has-component",
        "hasProperty": "has-property",
    }.get(node.reference_type)


def render_connectors_svg(node, style, triangles=True):
    """Draw the merged trunk + stubs from `node` down to its children, plus
    (optionally) a hollow UML triangle where the trunk meets node's bottom
    edge."""
    parts = []
    if not node.children:
        return parts

    trunk_x = node.cx
    last_cy = node.children[-1].cy
    start_y = node.bottom + TRI_H + 1.12
    parts.append(
        f'<line x1="{trunk_x:.0f}" y1="{start_y:.2f}" '
        f'x2="{trunk_x:.0f}" y2="{last_cy:.0f}" '
        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
    )
    for child in node.children:
        marker = reference_marker(child)
        marker_attr = f' marker-end="url(#{marker})"' if marker else ""
        parts.append(
            f'<line x1="{trunk_x:.0f}" y1="{child.cy:.0f}" '
            f'x2="{(child.x + child.w if child.x < trunk_x else child.x):.0f}" '
            f'y2="{child.cy:.0f}" stroke="{html.escape(style["arrow"], quote=True)}" '
            f'stroke-width="1"{marker_attr}/>'
        )

    if triangles and any(child.reference_type == "inheritance" for child in node.children):
        apex = (trunk_x, node.bottom + 1.12)
        bl = (trunk_x - TRI_W / 2, node.bottom + TRI_H + 1.12)
        br = (trunk_x + TRI_W / 2, node.bottom + TRI_H + 1.12)
        pts = f"{apex[0]:.2f},{apex[1]:.2f} {bl[0]:.2f},{bl[1]:.2f} {br[0]:.2f},{br[1]:.2f}"
        parts.append(
            f'<polygon points="{pts}" fill="white" '
            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1.5"/>'
        )

    return parts


def render_root_connectors_svg(root, style, triangles=True):
    """Root's children are spread horizontally: one shared horizontal bus at
    root.bottom + GAP_Y_ROOT/2, with a stub down from root and a stub down
    into each child, plus one triangle at root's own bottom edge."""
    if not root.children:
        return []

    parts = []
    bus_y = 83
    # stub from root down to the bus
    parts.append(
        f'<line x1="{root.cx:.0f}" y1="{root.bottom + TRI_H + 1.12:.2f}" '
        f'x2="{root.cx:.0f}" y2="{bus_y:.0f}" '
        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
    )
    xs = [c.cx for c in root.children]
    parts.append(
        f'<line x1="{min(xs):.0f}" y1="{bus_y:.0f}" '
        f'x2="{max(xs):.0f}" y2="{bus_y:.0f}" '
        f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"/>'
    )
    for child in root.children:
        marker = reference_marker(child)
        marker_attr = f' marker-end="url(#{marker})"' if marker else ""
        parts.append(
            f'<line x1="{child.cx:.0f}" y1="{bus_y:.0f}" '
            f'x2="{child.cx:.0f}" y2="{child.y:.0f}" '
            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1"'
            f'{marker_attr}/>'
        )

    if triangles and any(child.reference_type == "inheritance" for child in root.children):
        apex = (root.cx, root.bottom + 1.12)
        bl = (root.cx - TRI_W / 2, root.bottom + TRI_H + 1.12)
        br = (root.cx + TRI_W / 2, root.bottom + TRI_H + 1.12)
        pts = f"{apex[0]:.2f},{apex[1]:.2f} {bl[0]:.2f},{bl[1]:.2f} {br[0]:.2f},{br[1]:.2f}"
        parts.append(
            f'<polygon points="{pts}" fill="white" '
            f'stroke="{html.escape(style["arrow"], quote=True)}" stroke-width="1.5"/>'
        )

    return parts


def render_defs(shadow):
    parts = ["<defs>"]
    if shadow:
        parts.append(
            '<filter id="node-shadow" x="-20%" y="-20%" width="150%" height="150%">'
            '<feDropShadow dx="4" dy="5" stdDeviation="1.5" flood-color="#000000" '
            'flood-opacity="0.5"/></filter>'
        )
    parts.extend((
        '<marker id="has-type-definition" viewBox="0 0 10 8" markerWidth="10" '
        'markerHeight="8" refX="10" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L5,4 L0,8 Z M5,0 L10,4 L5,8 Z" fill="context-stroke"/></marker>',
        '<marker id="has-component" viewBox="0 0 4 8" markerWidth="4" '
        'markerHeight="8" refX="4" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M3,0 L3,8" fill="none" stroke="context-stroke" stroke-width="1"/></marker>',
        '<marker id="has-property" viewBox="0 0 7 8" markerWidth="7" '
        'markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M2,0 L2,8 M5,0 L5,8" fill="none" stroke="context-stroke" '
        'stroke-width="1"/></marker>',
    ))
    parts.append("</defs>")
    return "".join(parts)


def to_svg(root, triangles=True):
    W, H = layout(root)

    nodes = []
    connectors = []

    def walk(node, is_root=False):
        nodes.extend(render_node_svg(node, root.style, root.node_shadow))
        if is_root:
            connectors.extend(render_root_connectors_svg(node, root.style, triangles))
        else:
            connectors.extend(render_connectors_svg(node, root.style, triangles))
        for child in node.children:
            walk(child)

    walk(root, is_root=True)

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}px" height="{H}px" '
        f'viewBox="-0.5 -0.5 {W} {H}">\n'
        + render_defs(root.node_shadow) + '\n'
        + '<g>\n'
        + "\n".join(nodes + connectors) +
        '\n</g>\n</svg>\n'
    )
    return svg


# --- CLI ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("infile", help="input type-system file with '*'-depth nodes")
    ap.add_argument("-o", "--outfile", help="output SVG path (default: <infile>.svg)")
    ap.add_argument("--no-triangles", action="store_true", help="plain tree lines, no UML inheritance triangles")
    args = ap.parse_args()

    with open(args.infile, "r", encoding="utf-8") as f:
        text = f.read()

    root = parse(text)
    svg = to_svg(root, triangles=not args.no_triangles)

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
