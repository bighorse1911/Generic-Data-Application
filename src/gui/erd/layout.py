from __future__ import annotations

from dataclasses import dataclass

from src.gui.erd.common import _erd_error
from src.schema_project_model import ForeignKeySpec, SchemaProject, TableSpec


@dataclass(frozen=True)
class ERDNode:
    table_name: str
    lines: list[str]
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ERDEdge:
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str


def _fk_columns_by_table(project: SchemaProject) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for fk in project.foreign_keys:
        out.setdefault(fk.child_table, set()).add(fk.child_column)
    return out


def build_table_detail_lines(
    table: TableSpec,
    *,
    fk_columns: set[str],
    show_columns: bool,
    show_dtypes: bool,
) -> list[str]:
    if not show_columns:
        return []

    lines: list[str] = []
    for col in table.columns:
        tags: list[str] = []
        if col.primary_key:
            tags.append("PK")
        if col.name in fk_columns:
            tags.append("FK")
        tag_text = f"[{','.join(tags)}] " if tags else ""
        dtype_text = f": {col.dtype}" if show_dtypes else ""
        lines.append(f"{tag_text}{col.name}{dtype_text}")
    return lines


def _table_levels(project: SchemaProject) -> dict[str, int]:
    table_names = sorted(t.table_name for t in project.tables)
    parents_by_child: dict[str, set[str]] = {name: set() for name in table_names}
    for fk in project.foreign_keys:
        parents_by_child.setdefault(fk.child_table, set()).add(fk.parent_table)

    levels: dict[str, int] = {}
    for name in table_names:
        if not parents_by_child.get(name):
            levels[name] = 0

    progress = True
    while progress:
        progress = False
        for name in table_names:
            if name in levels:
                continue
            parents = parents_by_child.get(name, set())
            if parents and all(parent in levels for parent in parents):
                levels[name] = max(levels[parent] for parent in parents) + 1
                progress = True

    for name in table_names:
        levels.setdefault(name, 0)
    return levels


def build_erd_layout(
    project: SchemaProject,
    *,
    show_columns: bool,
    show_dtypes: bool,
    node_width: int = 300,
    header_height: int = 30,
    line_height: int = 18,
    margin: int = 32,
    column_gap: int = 110,
    row_gap: int = 24,
) -> tuple[list[ERDNode], list[ERDEdge], int, int]:
    table_map = {t.table_name: t for t in project.tables}
    levels = _table_levels(project)
    fk_columns_by_table = _fk_columns_by_table(project)

    names_by_level: dict[int, list[str]] = {}
    for table_name, level in levels.items():
        names_by_level.setdefault(level, []).append(table_name)
    for names in names_by_level.values():
        names.sort()

    nodes: list[ERDNode] = []
    max_y = margin
    max_level = max(levels.values(), default=0)

    for level in sorted(names_by_level.keys()):
        x = margin + level * (node_width + column_gap)
        y = margin
        for table_name in names_by_level[level]:
            table = table_map[table_name]
            lines = build_table_detail_lines(
                table,
                fk_columns=fk_columns_by_table.get(table_name, set()),
                show_columns=show_columns,
                show_dtypes=show_dtypes,
            )
            line_count = max(1, len(lines))
            height = header_height + 12 + (line_count * line_height)
            node = ERDNode(
                table_name=table_name,
                lines=lines,
                x=x,
                y=y,
                width=node_width,
                height=height,
            )
            nodes.append(node)
            y += height + row_gap
        max_y = max(max_y, y)

    edges = [
        ERDEdge(
            parent_table=fk.parent_table,
            parent_column=fk.parent_column,
            child_table=fk.child_table,
            child_column=fk.child_column,
        )
        for fk in sorted(
            project.foreign_keys,
            key=lambda fk: (fk.parent_table, fk.child_table, fk.parent_column, fk.child_column),
        )
    ]

    width = margin * 2 + (max_level + 1) * node_width + max_level * column_gap
    height = max(max_y + margin, margin * 2 + 200)
    return nodes, edges, width, height


def edge_label(edge: ERDEdge) -> str:
    return f"{edge.child_table}.{edge.child_column} -> {edge.parent_table}.{edge.parent_column}"


def node_anchor_y(node: ERDNode, *, table: TableSpec, column_name: str) -> int:
    header_base = node.y + 30 + 6
    for idx, col in enumerate(table.columns):
        if col.name == column_name:
            return int(header_base + idx * 18)
    return int(node.y + node.height / 2)


def table_for_edge(
    edge: ERDEdge,
    *,
    table_map: dict[str, TableSpec],
) -> tuple[TableSpec, TableSpec]:
    try:
        parent = table_map[edge.parent_table]
        child = table_map[edge.child_table]
    except KeyError as exc:
        raise ValueError(
            _erd_error(
                "Relationships",
                f"edge references unknown table '{exc.args[0]}'",
                "ensure FK tables exist in schema input",
            )
        ) from exc
    return parent, child


def relation_lines(project: SchemaProject) -> list[ForeignKeySpec]:
    return sorted(
        project.foreign_keys,
        key=lambda fk: (fk.parent_table, fk.child_table, fk.parent_column, fk.child_column),
    )


def apply_node_position_overrides(
    nodes: list[ERDNode],
    *,
    positions: dict[str, tuple[int, int]] | None,
) -> list[ERDNode]:
    if not positions:
        return list(nodes)

    out: list[ERDNode] = []
    for node in nodes:
        moved = positions.get(node.table_name)
        if moved is None:
            out.append(node)
            continue
        out.append(
            ERDNode(
                table_name=node.table_name,
                lines=node.lines,
                x=int(moved[0]),
                y=int(moved[1]),
                width=node.width,
                height=node.height,
            )
        )
    return out


def compute_diagram_size(
    nodes: list[ERDNode],
    *,
    min_width: int,
    min_height: int,
    margin: int = 32,
) -> tuple[int, int]:
    max_right = max((node.x + node.width for node in nodes), default=0)
    max_bottom = max((node.y + node.height for node in nodes), default=0)
    return max(min_width, max_right + margin), max(min_height, max_bottom + margin)
