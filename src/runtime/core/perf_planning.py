from __future__ import annotations

from src.schema_project_model import SchemaProject
from src.runtime.core.perf_profile import _performance_error
from src.runtime.core.perf_types import ChunkPlanEntry, ChunkPlanSummary, PerformanceProfile

def validate_performance_profile(project: SchemaProject, profile: PerformanceProfile) -> None:
    table_names = {table.table_name for table in project.tables}
    target_tables = profile.target_tables or tuple(table.table_name for table in project.tables)
    unknown_targets = [name for name in target_tables if name not in table_names]
    if unknown_targets:
        bad = ", ".join(sorted(unknown_targets))
        raise ValueError(
            _performance_error(
                "Target tables",
                f"unknown table selection ({bad})",
                "load a schema and use existing table names in target tables",
            )
        )

    unknown_override_tables = [name for name in profile.row_overrides if name not in table_names]
    if unknown_override_tables:
        bad = ", ".join(sorted(unknown_override_tables))
        raise ValueError(
            _performance_error(
                "Row overrides",
                f"contains unknown table names ({bad})",
                "use existing schema table names as row override keys",
            )
        )

    if not profile.strict_deterministic_chunking:
        raise ValueError(
            _performance_error(
                "Strict deterministic chunking",
                "cannot be disabled while deterministic generation is required",
                "enable strict deterministic chunking",
            )
        )

    page_cap = profile.preview_page_size * 1000
    if profile.preview_row_target > page_cap:
        raise ValueError(
            _performance_error(
                "Preview row target",
                f"value {profile.preview_row_target} exceeds cap {page_cap} for preview_page_size={profile.preview_page_size}",
                f"use preview row target <= {page_cap}, or increase preview page size",
            )
        )

    effective_rows: dict[str, int] = {table.table_name: table.row_count for table in project.tables}
    effective_rows.update(profile.row_overrides)
    for fk in project.foreign_keys:
        parent_rows = effective_rows.get(fk.parent_table, 0)
        min_required = parent_rows * fk.min_children
        child_override = profile.row_overrides.get(fk.child_table)
        if child_override is not None and child_override < min_required:
            raise ValueError(
                _performance_error(
                    f"Row overrides / {fk.child_table}",
                    (
                        f"override value {child_override} violates FK minimum for "
                        f"{fk.parent_table}.{fk.parent_column} -> {fk.child_table}.{fk.child_column} "
                        f"(requires at least {min_required} rows)"
                    ),
                    f"set row override for '{fk.child_table}' >= {min_required}, or lower parent row override",
                )
            )

def _selected_table_names(project: SchemaProject, profile: PerformanceProfile) -> tuple[str, ...]:
    if profile.target_tables:
        return profile.target_tables
    return tuple(table.table_name for table in project.tables)

def _topological_table_order(
    project: SchemaProject,
    selected_tables: tuple[str, ...],
) -> tuple[tuple[str, ...], dict[str, set[str]]]:
    selected_set = set(selected_tables)
    parents_by_child: dict[str, set[str]] = {name: set() for name in selected_tables}
    children_by_parent: dict[str, set[str]] = {name: set() for name in selected_tables}

    for fk in project.foreign_keys:
        if fk.parent_table not in selected_set or fk.child_table not in selected_set:
            continue
        if fk.parent_table == fk.child_table:
            continue
        parents_by_child[fk.child_table].add(fk.parent_table)
        children_by_parent[fk.parent_table].add(fk.child_table)

    indegree = {name: len(parents_by_child[name]) for name in selected_tables}
    ready = sorted(name for name, degree in indegree.items() if degree == 0)
    ordered: list[str] = []

    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(children_by_parent[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()

    if len(ordered) != len(selected_tables):
        unresolved = sorted(name for name in selected_tables if name not in ordered)
        unresolved_text = ", ".join(unresolved)
        raise ValueError(
            _performance_error(
                "Chunk plan",
                f"detected cyclic table dependencies ({unresolved_text})",
                "remove cyclic FK dependencies or select an acyclic table subset",
            )
        )

    return tuple(ordered), parents_by_child

def build_chunk_plan(project: SchemaProject, profile: PerformanceProfile) -> list[ChunkPlanEntry]:
    validate_performance_profile(project, profile)
    selected_tables = _selected_table_names(project, profile)
    table_map = {table.table_name: table for table in project.tables}
    ordered_tables, parents_by_child = _topological_table_order(project, selected_tables)

    effective_rows: dict[str, int] = {table.table_name: table.row_count for table in project.tables}
    effective_rows.update(profile.row_overrides)

    stage_by_table: dict[str, int] = {}
    entries: list[ChunkPlanEntry] = []
    for table_name in ordered_tables:
        parent_names = parents_by_child.get(table_name, set())
        if parent_names:
            stage = max(stage_by_table[parent] for parent in parent_names) + 1
        else:
            stage = 0
        stage_by_table[table_name] = stage

        table_rows = int(effective_rows.get(table_name, table_map[table_name].row_count))
        chunk_size = profile.chunk_size_rows
        chunk_count = (table_rows + chunk_size - 1) // chunk_size
        for chunk_offset in range(chunk_count):
            start_row = (chunk_offset * chunk_size) + 1
            end_row = min(table_rows, ((chunk_offset + 1) * chunk_size))
            rows_in_chunk = end_row - start_row + 1
            entries.append(
                ChunkPlanEntry(
                    table_name=table_name,
                    stage=stage,
                    chunk_index=chunk_offset + 1,
                    start_row=start_row,
                    end_row=end_row,
                    rows_in_chunk=rows_in_chunk,
                )
            )
    return entries

def summarize_chunk_plan(entries: list[ChunkPlanEntry]) -> ChunkPlanSummary:
    if not entries:
        return ChunkPlanSummary(
            total_chunks=0,
            total_rows=0,
            max_stage=0,
            table_count=0,
        )
    return ChunkPlanSummary(
        total_chunks=len(entries),
        total_rows=sum(entry.rows_in_chunk for entry in entries),
        max_stage=max(entry.stage for entry in entries),
        table_count=len({entry.table_name for entry in entries}),
    )

def _selected_tables_with_required_parents(
    project: SchemaProject,
    profile: PerformanceProfile,
) -> tuple[str, ...]:
    selected = set(_selected_table_names(project, profile))
    parent_by_child: dict[str, set[str]] = {}
    for fk in project.foreign_keys:
        parent_by_child.setdefault(fk.child_table, set()).add(fk.parent_table)

    changed = True
    while changed:
        changed = False
        current = list(selected)
        for table_name in current:
            for parent_name in parent_by_child.get(table_name, set()):
                if parent_name not in selected:
                    selected.add(parent_name)
                    changed = True

    ordered, _parents = _topological_table_order(project, tuple(sorted(selected)))
    return ordered
