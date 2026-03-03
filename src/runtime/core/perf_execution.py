from __future__ import annotations

import base64
import csv
import os
from dataclasses import replace
from pathlib import Path
from typing import Callable

from src.generator_project import generate_project_rows, generate_project_rows_streaming
from src.schema_project_model import SchemaProject, TableSpec
from src.storage_sqlite_project import create_tables, insert_project_rows
from src.runtime.core.perf_estimation import estimate_workload, summarize_estimates
from src.runtime.core.perf_planning import (
    _selected_table_names,
    _selected_tables_with_required_parents,
    build_chunk_plan,
    summarize_chunk_plan,
    validate_performance_profile,
)
from src.runtime.core.perf_profile import _performance_error
from src.runtime.core.perf_types import (
    BenchmarkResult,
    ChunkPlanEntry,
    PerformanceProfile,
    PerformanceRunCancelled,
    RuntimeEvent,
    StrategyRunResult,
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
        correlation_groups=table.correlation_groups,
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
        timeline_constraints=project.timeline_constraints,
        data_quality_profiles=project.data_quality_profiles,
        sample_profile_fits=project.sample_profile_fits,
        locale_identity_bundles=project.locale_identity_bundles,
    )

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
    effective_profile = replace(profile, target_tables=selected_tables)
    chunk_plan = build_chunk_plan(project, effective_profile)
    chunk_summary = summarize_chunk_plan(chunk_plan)
    chunk_entries_by_table: dict[str, list[ChunkPlanEntry]] = {}
    for entry in chunk_plan:
        chunk_entries_by_table.setdefault(entry.table_name, []).append(entry)

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
    rows_by_table: dict[str, list[dict[str, object]]] = {}
    csv_paths: dict[str, str] = {}
    sqlite_counts: dict[str, int] = {}
    rows_processed = 0
    total_rows = 0

    def _emit_progress_for_table(table_name: str) -> None:
        nonlocal rows_processed
        for entry in chunk_entries_by_table.get(table_name, []):
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

    if mode == "preview":
        rows_by_table_full = generate_project_rows(runtime_project)
        _ensure_not_cancelled(cancel_requested, "post-generation")
        rows_by_table = {
            table_name: list(rows_by_table_full.get(table_name, []))
            for table_name in selected_tables
        }
        for table_name in selected_tables:
            _ensure_not_cancelled(cancel_requested, "chunk processing")
            _emit_progress_for_table(table_name)
        total_rows = sum(len(rows) for rows in rows_by_table.values())
    else:
        sample_row_limit = max(0, int(profile.preview_row_target))

        if mode in {"sqlite", "all"}:
            assert output_sqlite_path is not None
            create_tables(output_sqlite_path, runtime_project)

        def _on_generated_table(table_name: str, rows: list[dict[str, object]]) -> None:
            nonlocal total_rows
            if table_name not in selected_set:
                return
            _ensure_not_cancelled(cancel_requested, f"table processing ({table_name})")

            if sample_row_limit > 0:
                rows_by_table[table_name] = list(rows[:sample_row_limit])

            if mode in {"csv", "all"}:
                table_paths = _write_rows_to_csv_folder(
                    {table_name: rows},
                    (table_name,),
                    output_csv_folder or "",
                    buffer_rows=profile.csv_buffer_rows,
                    on_event=on_event,
                    cancel_requested=cancel_requested,
                )
                csv_paths.update(table_paths)

            if mode in {"sqlite", "all"}:
                assert output_sqlite_path is not None
                inserted = insert_project_rows(
                    output_sqlite_path,
                    runtime_project,
                    {table_name: rows},
                    chunk_size=profile.sqlite_batch_size,
                )
                sqlite_counts[table_name] = int(inserted.get(table_name, 0))

            total_rows += len(rows)
            _emit_progress_for_table(table_name)

        generate_project_rows_streaming(
            runtime_project,
            on_table_rows=_on_generated_table,
        )

    if mode in {"sqlite", "all"}:
        for table_name in selected_tables:
            sqlite_counts.setdefault(table_name, 0)

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
