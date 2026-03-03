from __future__ import annotations

from src.gui.erd.layout import (
    apply_node_position_overrides,
    build_erd_layout,
    compute_diagram_size,
    edge_label,
    node_anchor_y,
    table_for_edge,
)
from src.schema_project_model import SchemaProject


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_erd_svg(
    project: SchemaProject,
    *,
    show_relationships: bool,
    show_columns: bool,
    show_dtypes: bool,
    node_positions: dict[str, tuple[int, int]] | None = None,
) -> str:
    nodes, edges, base_width, base_height = build_erd_layout(
        project,
        show_columns=show_columns,
        show_dtypes=show_dtypes,
    )
    nodes = apply_node_position_overrides(nodes, positions=node_positions)
    width, height = compute_diagram_size(nodes, min_width=base_width, min_height=base_height)
    node_by_table = {node.table_name: node for node in nodes}
    table_map = {table.table_name: table for table in project.tables}

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    lines.append(f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#f3f6fb" />')

    for node in nodes:
        x1 = node.x
        y1 = node.y
        x2 = node.x + node.width
        header_h = 30
        lines.append(
            f'  <rect x="{x1}" y="{y1}" width="{node.width}" height="{node.height}" fill="#ffffff" stroke="#556b8a" stroke-width="2" />'
        )
        lines.append(
            f'  <rect x="{x1}" y="{y1}" width="{node.width}" height="{header_h}" fill="#dae7f8" stroke="#556b8a" stroke-width="2" />'
        )
        lines.append(
            f'  <text x="{x1 + 8}" y="{y1 + 20}" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a2a44">{_xml_escape(node.table_name)}</text>'
        )

        detail_lines = node.lines if node.lines else ["(columns hidden)"]
        y = y1 + 48
        for line in detail_lines:
            lines.append(
                f'  <text x="{x1 + 8}" y="{y}" font-family="Consolas, Courier New, monospace" font-size="11" fill="#27374d">{_xml_escape(line)}</text>'
            )
            y += 18
        _ = x2

    if show_relationships:
        for edge in edges:
            parent_node = node_by_table.get(edge.parent_table)
            child_node = node_by_table.get(edge.child_table)
            if parent_node is None or child_node is None:
                continue
            try:
                parent_table, child_table = table_for_edge(edge, table_map=table_map)
            except ValueError:
                continue

            if show_columns:
                y1 = node_anchor_y(parent_node, table=parent_table, column_name=edge.parent_column)
                y2 = node_anchor_y(child_node, table=child_table, column_name=edge.child_column)
            else:
                y1 = int(parent_node.y + parent_node.height / 2)
                y2 = int(child_node.y + child_node.height / 2)

            x1 = parent_node.x + parent_node.width
            x2 = child_node.x
            mid_x = int((x1 + x2) / 2)
            path = f"M {x1} {y1} L {mid_x} {y1} L {mid_x} {y2} L {x2} {y2}"
            lines.append(
                f'  <path d="{path}" fill="none" stroke="#1f5a95" stroke-width="2" marker-end="url(#arrow)" />'
            )
            label = _xml_escape(edge_label(edge))
            lines.append(
                f'  <text x="{mid_x + 6}" y="{int((y1 + y2) / 2) - 7}" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="#1f5a95">{label}</text>'
            )

    lines.insert(
        3,
        '  <defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#1f5a95" /></marker></defs>',
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"
