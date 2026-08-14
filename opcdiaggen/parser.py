# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

import re

from .model import Node, Reference, Style, infer_reference_type

REFERENCE_TYPES = {
    "inheritance": "inheritance",
    "hastypedefinition": "hasTypeDefinition",
    "hascomponent": "hasComponent",
    "hasproperty": "hasProperty",
    "organizes": "Organizes",
}
NODE_CLASSES = {"obj", "objtype", "var", "vartype", "method", "reftype", "datatype", "view"}


def parse(text):
    stack = []
    root = None
    style = Style()
    in_node_skinparam = False
    branch_group = 0
    pending_group_break = False
    node_specs = []
    nodes_by_id = {}

    for raw in text.splitlines():
        stripped = raw.rstrip().strip()
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
        if lower.startswith("ref "):
            ref = re.fullmatch(
                r"ref\s+(\S+)(?:\s+\[([tblr])\])?\s+(\S+)\s+-\s+(\S+)(?:\s+\[([tblr])\])?",
                stripped,
                re.I,
            )
            if ref:
                node_specs.append(("additional", ref.groups()))
            continue
        setting = re.match(r"^(?:skinparam\s+)?([A-Za-z]+)\s+(.+)$", stripped)
        if setting:
            _apply_setting(style, setting.group(1).lower(), setting.group(2).strip(), in_node_skinparam)
            continue
        if not stripped.startswith("*"):
            ref = re.fullmatch(r"ref\s+(\S+)(?:\s+\[([tblr])\])?\s+(\S+)\s+-\s+(\S+)(?:\s+\[([tblr])\])?", stripped, re.I)
            if ref:
                node_specs.append(("additional", ref.groups()))
            continue
        match = re.match(r"^(\*+)\s*(.*)$", stripped)
        if not match:
            continue
        depth = len(match.group(1))
        tokens = match.group(2).split(None, 2)
        explicit_reference = None
        if tokens and tokens[0].lower() in REFERENCE_TYPES:
            explicit_reference = REFERENCE_TYPES[tokens.pop(0).lower()]
        nodeclass = tokens.pop(0).lower() if tokens and tokens[0].lower() in NODE_CLASSES else "objtype"
        label_match = re.fullmatch(r'"((?:[^"\\]|\\.)*)"\s*(?:\{#([A-Za-z_][A-Za-z0-9_-]*)\})?', " ".join(tokens))
        if not label_match:
            raise ValueError(f"node label must be quoted near: {stripped!r}")
        label = (label_match.group(1).replace(r"\n", "\n").replace(r'\"', '"').replace(r"\\", "\\"))
        node = Node(label, nodeclass, explicit_reference, branch_group, label_match.group(2))
        if node.node_id:
            if node.node_id in nodes_by_id:
                raise ValueError(f"duplicate node id: {node.node_id!r}")
            nodes_by_id[node.node_id] = node
        if depth == 1:
            root = node
            stack = [(depth, node)]
            continue
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
        node.reference_type = node.reference_type or infer_reference_type(parent.nodeclass, node.nodeclass)
        parent.add_child(node)
        reference = Reference(node.reference_type, parent, node, hierarchical=True)
        parent.outgoing_references.append(reference)
        stack.append((depth, node))

    if root is None:
        raise ValueError("no root node found (expected a line starting with a single '*')")
    root.style = style
    for kind, groups in node_specs:
        if kind != "additional":
            continue
        ref_type, source_anchor, source_id, target_id, target_anchor = groups
        if source_id not in nodes_by_id or target_id not in nodes_by_id:
            raise ValueError(f"unknown node id in reference: {source_id!r}, {target_id!r}")
        reference = Reference(ref_type, nodes_by_id[source_id], nodes_by_id[target_id], False)
        reference.source_anchor = _direction(source_anchor)
        reference.target_anchor = _direction(target_anchor)
        reference.source.outgoing_references.append(reference)
        root.additional_references.append(reference)
    return root


def _apply_setting(style, key, value, in_node_skinparam):
    if key.startswith("node"):
        key = key[4:]
    if not in_node_skinparam and key not in ("minwidth", "width"):
        return
    names = {
        "backgroundcolor": "type_fill", "fill": "type_fill", "typebackgroundcolor": "type_fill", "typefill": "type_fill",
        "instancebackgroundcolor": "instance_fill_start", "instancefill": "instance_fill_start",
        "instancebackgroundcolorend": "instance_fill_end", "instancefillend": "instance_fill_end",
        "bordercolor": "stroke", "stroke": "stroke", "fontcolor": "text", "textcolor": "text",
        "fontname": "font", "fontfamily": "font", "arrowcolor": "arrow", "linecolor": "arrow",
    }
    if key in names:
        setattr(style, names[key], value)
    elif key in ("minwidth", "width"):
        style.min_width = float(value)
    elif key in ("strokewidth", "linewidth"):
        style.stroke_width = float(value)


def _direction(value):
    from .model import Direction
    return {"t": Direction.TOP, "b": Direction.BOTTOM,
            "l": Direction.LEFT, "r": Direction.RIGHT}.get(value)
