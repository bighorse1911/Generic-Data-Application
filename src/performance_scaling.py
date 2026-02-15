from __future__ import annotations

import base64
import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from typing import Callable

from src.generator_project import generate_project_rows
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.storage_sqlite_project import create_tables, insert_project_rows

OUTPUT_MODES: tuple[str, ...] = ("preview", "csv", "sqlite", "all")
FK_CACHE_MODES: tuple[str, ...] = ("auto", "memory", "disk_spill")


def _performance_error(field: str, issue: str, hint: str) -> str:
    return f"Performance Workbench / {field}: {issue}. Fix: {hint}."


def _parse_bounded_int(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
    hint: str,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_performance_error(field, "must be an integer", hint)) from exc
    if parsed < minimum:
        raise ValueError(_performance_error(field, f"value {parsed} must be >= {minimum}", hint))
    if parsed > maximum:
        raise ValueError(_performance_error(field, f"value {parsed} must be <= {maximum}", hint))
    return parsed


def _parse_output_mode(value: Any) -> str:
    text = str(value).strip().lower()
    if text not in OUTPUT_MODES:
        allowed = ", ".join(OUTPUT_MODES)
        raise ValueError(
            _performance_error(
                "Output mode",
                f"unsupported output mode '{value}'",
                f"choose one of: {allowed}",
            )
        )
    return text


def _parse_fk_cache_mode(value: Any) -> str:
    text = str(value).strip().lower()
    if text not in FK_CACHE_MODES:
        allowed = ", ".join(FK_CACHE_MODES)
        raise ValueError(
            _performance_error(
                "FK cache mode",
                f"unsupported FK cache mode '{value}'",
                f"choose one of: {allowed}",
            )
        )
    return text


def _parse_strict_deterministic_chunking(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    raise ValueError(
        _performance_error(
            "Strict deterministic chunking",
            "must be true or false",
            "set strict deterministic chunking to true or false",
        )
    )


def _parse_target_tables(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if text == "":
        return ()
    parts = [part.strip() for part in text.split(",") if part.strip() != ""]
    if len(parts) != len(set(parts)):
        raise ValueError(
            _performance_error(
                "Target tables",
                "contains duplicate table names",
                "list each table name once, separated by commas",
            )
        )
    return tuple(parts)


def _parse_row_overrides_json(value: Any) -> dict[str, int]:
    if value is None:
        return {}
    text = str(value).strip()
    if text == "":
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            _performance_error(
                "Row overrides JSON",
                f"invalid JSON at line {exc.lineno}, column {exc.colno}",
                "enter JSON object like {\"orders\": 250000}",
            )
        ) from exc
    if not isinstance(decoded, dict):
        raise ValueError(
            _performance_error(
                "Row overrides JSON",
                "must be a JSON object",
                "enter JSON object mapping table name to positive integer row count",
            )
        )
    out: dict[str, int] = {}
    for raw_name, raw_rows in decoded.items():
        if not isinstance(raw_name, str) or raw_name.strip() == "":
            raise ValueError(
                _performance_error(
                    "Row overrides JSON",
                    "contains an empty table name key",
                    "use non-empty string keys for table names",
                )
            )
        clean_name = raw_name.strip()
        out[clean_name] = _parse_bounded_int(
            raw_rows,
            field=f"Row override / {clean_name}",
            minimum=1,
            maximum=10_000_000,
            hint="set a positive whole-number row count <= 10000000",
        )
    return out


@dataclass(frozen=True)
class PerformanceProfile:
    target_tables: tuple[str, ...] = ()
    row_overrides: dict[str, int] = field(default_factory=dict)
    preview_row_target: int = 500
    output_mode: str = OUTPUT_MODES[0]
    chunk_size_rows: int = 10_000
    preview_page_size: int = 500
    sqlite_batch_size: int = 5_000
    csv_buffer_rows: int = 5_000
    fk_cache_mode: str = FK_CACHE_MODES[0]
    strict_deterministic_chunking: bool = True


@dataclass(frozen=True)
class WorkloadEstimate:
    table_name: str
    estimated_rows: int
    estimated_memory_mb: float
    estimated_write_mb: float
    estimated_seconds: float
    risk_level: str
    recommendation: str


@dataclass(frozen=True)
class WorkloadSummary:
    total_rows: int
    total_memory_mb: float
    total_write_mb: float
    total_seconds: float
    highest_risk: str


@dataclass(frozen=True)
class ChunkPlanEntry:
    table_name: str
    stage: int
    chunk_index: int
    start_row: int
    end_row: int
    rows_in_chunk: int


@dataclass(frozen=True)
class ChunkPlanSummary:
    total_chunks: int
    total_rows: int
    max_stage: int
    table_count: int


@dataclass(frozen=True)
class RuntimeEvent:
    kind: str
    table_name: str | None = None
    stage: int | None = None
    chunk_index: int | None = None
    total_chunks: int = 0
    rows_processed: int = 0
    total_rows: int = 0
    message: str = ""


@dataclass(frozen=True)
class BenchmarkResult:
    selected_tables: tuple[str, ...]
    estimates: list[WorkloadEstimate]
    estimate_summary: WorkloadSummary
    chunk_plan: list[ChunkPlanEntry]
    chunk_summary: ChunkPlanSummary


@dataclass(frozen=True)
class StrategyRunResult:
    selected_tables: tuple[str, ...]
    rows_by_table: dict[str, list[dict[str, object]]]
    csv_paths: dict[str, str]
    sqlite_counts: dict[str, int]
    total_rows: int


class PerformanceRunCancelled(RuntimeError):
    pass


def build_performance_profile(
    *,
    target_tables_value: Any,
    row_overrides_json_value: Any,
    preview_row_target_value: Any,
    output_mode_value: Any,
    chunk_size_rows_value: Any,
    preview_page_size_value: Any,
    sqlite_batch_size_value: Any,
    csv_buffer_rows_value: Any,
    fk_cache_mode_value: Any,
    strict_deterministic_chunking_value: Any,
) -> PerformanceProfile:
    return PerformanceProfile(
        target_tables=_parse_target_tables(target_tables_value),
        row_overrides=_parse_row_overrides_json(row_overrides_json_value),
        preview_row_target=_parse_bounded_int(
            preview_row_target_value,
            field="Preview row target",
            minimum=1,
            maximum=200_000,
            hint="set a positive whole number <= 200000",
        ),
        output_mode=_parse_output_mode(output_mode_value),
        chunk_size_rows=_parse_bounded_int(
            chunk_size_rows_value,
            field="Chunk size rows",
            minimum=1,
            maximum=1_000_000,
            hint="set a positive whole number <= 1000000",
        ),
        preview_page_size=_parse_bounded_int(
            preview_page_size_value,
            field="Preview page size",
            minimum=1,
            maximum=20_000,
            hint="set a positive whole number <= 20000",
        ),
        sqlite_batch_size=_parse_bounded_int(
            sqlite_batch_size_value,
            field="SQLite batch size",
            minimum=1,
            maximum=1_000_000,
            hint="set a positive whole number <= 1000000",
        ),
        csv_buffer_rows=_parse_bounded_int(
            csv_buffer_rows_value,
            field="CSV buffer rows",
            minimum=1,
            maximum=1_000_000,
            hint="set a positive whole number <= 1000000",
        ),
        fk_cache_mode=_parse_fk_cache_mode(fk_cache_mode_value),
        strict_deterministic_chunking=_parse_strict_deterministic_chunking(
            strict_deterministic_chunking_value
        ),
    )


def _risk_priority(level: str) -> int:
    if level == "high":
        return 3
    if level == "medium":
        return 2
    return 1


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


def estimate_workload(project: SchemaProject, profile: PerformanceProfile) -> list[WorkloadEstimate]:
    table_map = {table.table_name: table for table in project.tables}
    selected = profile.target_tables or tuple(table.table_name for table in project.tables)
    estimates: list[WorkloadEstimate] = []
    for table_name in selected:
        table = table_map[table_name]
        row_count = int(profile.row_overrides.get(table_name, table.row_count))
        column_count = max(1, len(table.columns))
        estimated_memory_mb = round((row_count * column_count * 48.0) / (1024.0 * 1024.0), 3)
        estimated_write_mb = round((row_count * column_count * 24.0) / (1024.0 * 1024.0), 3)
        complexity_multiplier = 1.0 + (max(0, column_count - 4) * 0.08)
        estimated_seconds = round((row_count * complexity_multiplier) / 75_000.0, 3)

        if estimated_memory_mb >= 512.0 or estimated_seconds >= 20.0:
            risk = "high"
            recommendation = "Reduce row overrides or split workload into smaller chunks."
        elif estimated_memory_mb >= 128.0 or estimated_seconds >= 5.0:
            risk = "medium"
            recommendation = "Review chunk_size_rows and preview scope before full generation."
        else:
            risk = "low"
            recommendation = "Current profile is suitable for phase-1 guided execution."

        if row_count > (profile.chunk_size_rows * 4):
            recommendation = "Row target is large relative to chunk size. Consider increasing chunk_size_rows."

        estimates.append(
            WorkloadEstimate(
                table_name=table_name,
                estimated_rows=row_count,
                estimated_memory_mb=estimated_memory_mb,
                estimated_write_mb=estimated_write_mb,
                estimated_seconds=estimated_seconds,
                risk_level=risk,
                recommendation=recommendation,
            )
        )
    return estimates


def summarize_estimates(estimates: list[WorkloadEstimate]) -> WorkloadSummary:
    if not estimates:
        return WorkloadSummary(
            total_rows=0,
            total_memory_mb=0.0,
            total_write_mb=0.0,
            total_seconds=0.0,
            highest_risk="low",
        )
    highest_risk = max((estimate.risk_level for estimate in estimates), key=_risk_priority)
    return WorkloadSummary(
        total_rows=sum(estimate.estimated_rows for estimate in estimates),
        total_memory_mb=round(sum(estimate.estimated_memory_mb for estimate in estimates), 3),
        total_write_mb=round(sum(estimate.estimated_write_mb for estimate in estimates), 3),
        total_seconds=round(sum(estimate.estimated_seconds for estimate in estimates), 3),
        highest_risk=highest_risk,
    )


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


def _clone_table_with_row_count(table: TableSpec, row_count: int) -> TableSpec:
    return TableSpec(
        table_name=table.table_name,
        columns=table.columns,
        row_count=row_count,
        business_key=table.business_key,
        business_key_unique_count=table.business_key_unique_count,
        business_key_static_columns=table.business_key_static_columns,
        business_key_changing_columns=table.business_key_changing_columns,
        scd_mode=table.scd_mode,
        scd_tracked_columns=table.scd_tracked_columns,
        scd_active_from_column=table.scd_active_from_column,
        scd_active_to_column=table.scd_active_to_column,
    )


def _clone_project_with_row_overrides(project: SchemaProject, overrides: dict[str, int]) -> SchemaProject:
    if not overrides:
        return project
    tables = []
    for table in project.tables:
        row_count = int(overrides.get(table.table_name, table.row_count))
        tables.append(_clone_table_with_row_count(table, row_count))
    return SchemaProject(
        name=project.name,
        seed=project.seed,
        tables=tables,
        foreign_keys=project.foreign_keys,
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


def _run_error(issue: str, hint: str) -> str:
    return _performance_error("Run", issue, hint)


def _emit_event(on_event: Callable[[RuntimeEvent], None] | None, event: RuntimeEvent) -> None:
    if on_event is None:
        return
    on_event(event)


def _ensure_not_cancelled(cancel_requested: Callable[[], bool] | None, phase: str) -> None:
    if cancel_requested is None:
        return
    if cancel_requested():
        raise PerformanceRunCancelled(
            _performance_error(
                "Cancel",
                f"run was cancelled during {phase}",
                "restart benchmark/generation when ready",
            )
        )


def run_performance_benchmark(
    project: SchemaProject,
    profile: PerformanceProfile,
    *,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> BenchmarkResult:
    validate_performance_profile(project, profile)
    _ensure_not_cancelled(cancel_requested, "benchmark setup")

    selected_tables = _selected_table_names(project, profile)
    estimates = estimate_workload(project, profile)
    estimate_summary = summarize_estimates(estimates)
    chunk_plan = build_chunk_plan(project, profile)
    chunk_summary = summarize_chunk_plan(chunk_plan)

    _emit_event(
        on_event,
        RuntimeEvent(
            kind="started",
            total_chunks=chunk_summary.total_chunks,
            total_rows=chunk_summary.total_rows,
            message="Benchmark started.",
        ),
    )

    rows_processed = 0
    for entry in chunk_plan:
        _ensure_not_cancelled(cancel_requested, "benchmark processing")
        rows_processed += entry.rows_in_chunk
        _emit_event(
            on_event,
            RuntimeEvent(
                kind="progress",
                table_name=entry.table_name,
                stage=entry.stage,
                chunk_index=entry.chunk_index,
                total_chunks=chunk_summary.total_chunks,
                rows_processed=rows_processed,
                total_rows=chunk_summary.total_rows,
                message="Benchmark progress.",
            ),
        )

    _emit_event(
        on_event,
        RuntimeEvent(
            kind="run_done",
            total_chunks=chunk_summary.total_chunks,
            rows_processed=chunk_summary.total_rows,
            total_rows=chunk_summary.total_rows,
            message="Benchmark complete.",
        ),
    )

    return BenchmarkResult(
        selected_tables=selected_tables,
        estimates=estimates,
        estimate_summary=estimate_summary,
        chunk_plan=chunk_plan,
        chunk_summary=chunk_summary,
    )


def _csv_export_value(value: object) -> object:
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def _write_rows_to_csv_folder(
    rows_by_table: dict[str, list[dict[str, object]]],
    table_order: tuple[str, ...],
    output_folder: str,
    *,
    buffer_rows: int,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> dict[str, str]:
    if output_folder.strip() == "":
        raise ValueError(_run_error("CSV output folder is required", "choose an output folder for CSV export"))
    folder_path = Path(output_folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    out_paths: dict[str, str] = {}
    for table_name in table_order:
        _ensure_not_cancelled(cancel_requested, f"CSV export ({table_name})")
        rows = rows_by_table.get(table_name, [])
        if not rows:
            continue
        cols = list(rows[0].keys())
        out_file = folder_path / f"{table_name}.csv"
        with out_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(cols)
            batch: list[list[object]] = []
            for idx, row in enumerate(rows, start=1):
                batch.append([_csv_export_value(row.get(col)) for col in cols])
                if len(batch) >= buffer_rows:
                    writer.writerows(batch)
                    batch = []
                if idx % max(1, buffer_rows) == 0:
                    _emit_event(
                        on_event,
                        RuntimeEvent(
                            kind="table_done",
                            table_name=table_name,
                            rows_processed=idx,
                            total_rows=len(rows),
                            message=f"CSV export progress for {table_name}.",
                        ),
                    )
                    _ensure_not_cancelled(cancel_requested, f"CSV export ({table_name})")
            if batch:
                writer.writerows(batch)
        out_paths[table_name] = os.fspath(out_file)
    return out_paths


def run_generation_with_strategy(
    project: SchemaProject,
    profile: PerformanceProfile,
    *,
    output_csv_folder: str | None = None,
    output_sqlite_path: str | None = None,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> StrategyRunResult:
    validate_performance_profile(project, profile)
    _ensure_not_cancelled(cancel_requested, "generation setup")

    selected_tables = _selected_tables_with_required_parents(project, profile)
    selected_set = set(selected_tables)
    chunk_plan = build_chunk_plan(project, profile)
    chunk_summary = summarize_chunk_plan(chunk_plan)

    mode = profile.output_mode
    if mode in {"csv", "all"} and (output_csv_folder is None or output_csv_folder.strip() == ""):
        raise ValueError(
            _run_error(
                "CSV output mode selected without output folder",
                "choose an output folder before running generation",
            )
        )
    if mode in {"sqlite", "all"} and (output_sqlite_path is None or output_sqlite_path.strip() == ""):
        raise ValueError(
            _run_error(
                "SQLite output mode selected without database path",
                "choose a SQLite .db output path before running generation",
            )
        )

    _emit_event(
        on_event,
        RuntimeEvent(
            kind="started",
            total_chunks=chunk_summary.total_chunks,
            total_rows=chunk_summary.total_rows,
            message="Generation with strategy started.",
        ),
    )

    runtime_project = _clone_project_with_row_overrides(project, profile.row_overrides)
    rows_by_table_full = generate_project_rows(runtime_project)
    _ensure_not_cancelled(cancel_requested, "post-generation")

    rows_by_table = {
        table_name: list(rows_by_table_full.get(table_name, []))
        for table_name in selected_tables
    }

    rows_processed = 0
    for entry in chunk_plan:
        if entry.table_name not in selected_set:
            continue
        _ensure_not_cancelled(cancel_requested, "chunk processing")
        rows_processed += entry.rows_in_chunk
        _emit_event(
            on_event,
            RuntimeEvent(
                kind="progress",
                table_name=entry.table_name,
                stage=entry.stage,
                chunk_index=entry.chunk_index,
                total_chunks=chunk_summary.total_chunks,
                rows_processed=rows_processed,
                total_rows=chunk_summary.total_rows,
                message="Generation progress.",
            ),
        )

    csv_paths: dict[str, str] = {}
    if mode in {"csv", "all"}:
        csv_paths = _write_rows_to_csv_folder(
            rows_by_table,
            selected_tables,
            output_csv_folder or "",
            buffer_rows=profile.csv_buffer_rows,
            on_event=on_event,
            cancel_requested=cancel_requested,
        )

    sqlite_counts: dict[str, int] = {}
    if mode in {"sqlite", "all"}:
        assert output_sqlite_path is not None
        create_tables(output_sqlite_path, runtime_project)
        sqlite_counts = insert_project_rows(
            output_sqlite_path,
            runtime_project,
            rows_by_table,
            chunk_size=profile.sqlite_batch_size,
        )

    total_rows = sum(len(rows) for rows in rows_by_table.values())
    _emit_event(
        on_event,
        RuntimeEvent(
            kind="run_done",
            total_chunks=chunk_summary.total_chunks,
            rows_processed=total_rows,
            total_rows=total_rows,
            message="Generation with strategy complete.",
        ),
    )

    return StrategyRunResult(
        selected_tables=selected_tables,
        rows_by_table=rows_by_table,
        csv_paths=csv_paths,
        sqlite_counts=sqlite_counts,
        total_rows=total_rows,
    )
