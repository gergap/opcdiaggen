# SPDX-FileCopyrightText: 2026 Gerhard Gappmeier <gerhard.gappmeier@ascolab.com>
# SPDX-License-Identifier: GPL-3.0-only

import html

from .connectors import choose_additional_anchors, walk
from .layout import layout
from .routing import LibavoidRouter

FONT_SIZE = 12
TRI_W, TRI_H = 7, 7


class SvgRenderer:
    def __init__(self, router=None, show_junctions=False):
        self.router = router or LibavoidRouter()
        self.show_junctions = show_junctions

    def render(self, root):
        width, height = layout(root)
        choose_additional_anchors(root)
        nodes = list(walk(root))
        hierarchy = [path for node in nodes for path in self._hierarchy_paths(node)]
        extra = self._additional_paths(root, nodes, hierarchy)
        style = root.style
        body = [self._node(node, style) for node in nodes]
        if self.show_junctions:
            body.extend(self._junction(junction, style)
                        for node in nodes for junction in node.junctions)
        body.extend(self._line_path(path, style.arrow, self._marker(reference) if reference else None)
                    for reference, path in hierarchy)
        body.extend(extra)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}px" height="{height}px" '
            f'viewBox="-0.5 -0.5 {width} {height}">\n'
            + self._defs(style) + '\n<g>\n'
            + "\n".join(body) + '\n</g>\n</svg>\n'
        )

    @staticmethod
    def _junction(junction, style):
        return (
            f'<circle cx="{junction.x:.0f}" cy="{junction.y:.0f}" r="4" '
            f'fill="{html.escape(style.arrow, quote=True)}"/>'
        )

    def _hierarchy_paths(self, node):
        """Return one source segment and one shared trunk per junction."""
        paths = []
        for junction in node.junctions:
            source = self._junction_boundary(junction)
            paths.append((None, [source, (junction.x, junction.y)]))
            references = junction.references
            if not references:
                continue
            if junction.direction.value in ("t", "b"):
                if references[0].reference_type in ("hasProperty", "hasComponent", "Organizes"):
                    first = references[0].target
                    trunk = first.x - 20 if first.x >= node.x else first.x + first.w + 20
                    trunk_bottom = max(reference.target.cy for reference in references)
                    paths.append((None, [(junction.x, junction.y), (trunk, junction.y), (trunk, trunk_bottom)]))
                    for reference in references:
                        target = reference.target
                        boundary = target.x if target.x >= node.x else target.x + target.w
                        paths.append((reference, [(trunk, target.cy), (boundary, target.cy)]))
                else:
                    approach = min(reference.target.y for reference in references) - 20
                    paths.append((None, [(junction.x, junction.y), (junction.x, approach)]))
                    for reference in references:
                        target = reference.target
                        paths.append((reference, [(junction.x, approach), (target.cx, approach), (target.cx, target.y)]))
        return paths

    @staticmethod
    def _junction_boundary(junction):
        node = junction.node
        if junction.direction.value == "t":
            return node.cx, node.y
        if junction.direction.value == "b":
            return node.cx, node.bottom
        if junction.direction.value == "l":
            return node.x, node.cy
        return node.x + node.w, node.cy

    def _additional_paths(self, root, nodes, hierarchy):
        if not root.additional_references:
            return []
        fixed = [[point for point in path] for _, path in hierarchy]
        try:
            routes = self.router.route(root.additional_references, nodes, fixed)
        except Exception:
            return []
        result = []
        for reference in root.additional_references:
            path = routes.get(reference)
            if not path:
                continue
            result.append(self._line_path(path, root.style.arrow, "additional-reference", reference.reference_type))
        return result

    @staticmethod
    def _marker(reference):
        return {"hasComponent": "has-component", "hasProperty": "has-property", "Organizes": "organizes"}.get(reference.reference_type)

    @staticmethod
    def _line_path(points, color, marker=None, label=None):
        if len(points) < 2:
            return ""
        commands = [f"M {points[0][0]:.0f},{points[0][1]:.0f}"]
        commands.extend(f"L {x:.0f},{y:.0f}" for x, y in points[1:])
        marker_attr = f' marker-end="url(#{marker})"' if marker else ""
        path = f'<path d="{" ".join(commands)}" fill="none" stroke="{html.escape(color, quote=True)}" stroke-width="1.3" stroke-linecap="round"{marker_attr}/>'
        if label:
            longest = max(zip(points, points[1:]), key=lambda segment: abs(segment[1][0] - segment[0][0]) + abs(segment[1][1] - segment[0][1]))
            first, second = longest
            x = (first[0] + second[0]) / 2 if first[1] == second[1] else min(first[0], second[0]) + 4
            y = first[1] - 4 if first[1] == second[1] else (first[1] + second[1]) / 2
            path += f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="middle" font-family="Helvetica" font-size="10">{html.escape(label)}</text>'
        return path

    @staticmethod
    def _node(node, style):
        fill = "url(#instance-fill)" if node.nodeclass in ("obj", "var", "method", "view") else style.type_fill
        if node.nodeclass == "method":
            shape = f'<ellipse cx="{node.cx:.0f}" cy="{node.cy:.0f}" rx="{node.w / 2:.0f}" ry="{node.h / 2:.0f}"'
            shape += f' fill="{html.escape(fill, quote=True)}" stroke="{html.escape(style.stroke, quote=True)}" stroke-width="{style.stroke_width:g}"/>'
        else:
            shape = f'<rect x="{node.x:.0f}" y="{node.y:.0f}" width="{node.w:.0f}" height="{node.h:.0f}" fill="{html.escape(fill, quote=True)}" stroke="{html.escape(style.stroke, quote=True)}" stroke-width="{style.stroke_width:g}"/>'
        lines = []
        for index, line in enumerate(node.label.split("\n")):
            escaped = html.escape(line)
            lines.append(f'<tspan x="{node.cx:.0f}" dy="{0 if index == 0 else 14}">{escaped}</tspan>')
        text_y = node.cy + 4 - (len(lines) - 1) * 7
        return f'<g>{shape}<text x="{node.cx:.0f}" y="{text_y:.1f}" text-anchor="middle" font-family="{html.escape(style.font, quote=True)}" font-size="{FONT_SIZE}">{"".join(lines)}</text></g>'

    @staticmethod
    def _defs(style):
        return (
            '<defs><linearGradient id="instance-fill" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{style.instance_fill_start}"/><stop offset="100%" stop-color="{style.instance_fill_end}"/>'
            '</linearGradient>'
            '<marker id="has-component" viewBox="0 0 6 12" markerWidth="6" markerHeight="12" refX="6" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M4.5,0 L4.5,12" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker>'
            '<marker id="has-property" viewBox="0 0 10.5 12" markerWidth="10.5" markerHeight="12" refX="10.5" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M3,0 L3,12 M6,0 L6,12" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker>'
            '<marker id="organizes" viewBox="0 0 15 12" markerWidth="15" markerHeight="12" refX="15" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L15,6 L0,12" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker>'
            '<marker id="additional-reference" viewBox="0 0 15 12" markerWidth="15" markerHeight="12" refX="15" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L15,6 L0,12" fill="none" stroke="context-stroke" stroke-width="1.3"/></marker></defs>'
        )


def to_svg(root, show_junctions=False):
    return SvgRenderer(show_junctions=show_junctions).render(root)
