from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.gui_v2.viewmodels import RunCenterViewModel
from src.multiprocessing_runtime import MultiprocessConfig
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunResult
from src.multiprocessing_runtime import PartitionPlanEntry
from src.multiprocessing_runtime import build_multiprocess_config
from src.multiprocessing_runtime import build_partition_plan
from src.multiprocessing_runtime import run_generation_with_multiprocessing
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import PerformanceProfile
from src.performance_scaling import RuntimeEvent
from src.performance_scaling import WorkloadEstimate
from src.performance_scaling import WorkloadSummary
from src.performance_scaling import build_performance_profile
from src.performance_scaling import estimate_workload
from src.performance_scaling import run_performance_benchmark
from src.performance_scaling import summarize_estimates
from src.performance_scaling import validate_performance_profile
from src.schema_project_model import SchemaProject


@dataclass(frozen=True)
class RunCenterDiagnostics:
    estimates: list[WorkloadEstimate]
    summary: WorkloadSummary


def build_profile_from_viewmodel(viewmodel: RunCenterViewModel) -> PerformanceProfile:
    return build_performance_profile(
        target_tables_value=viewmodel.target_tables,
        row_overrides_json_value=viewmodel.row_overrides_json,
        preview_row_target_value=viewmodel.preview_row_target,
        output_mode_value=viewmodel.output_mode,
        chunk_size_rows_value=viewmodel.chunk_size_rows,
        preview_page_size_value=viewmodel.preview_page_size,
        sqlite_batch_size_value=viewmodel.sqlite_batch_size,
        csv_buffer_rows_value=viewmodel.csv_buffer_rows,
        fk_cache_mode_value=viewmodel.fk_cache_mode,
        strict_deterministic_chunking_value=viewmodel.strict_deterministic_chunking,
    )


def build_config_from_viewmodel(viewmodel: RunCenterViewModel) -> MultiprocessConfig:
    return build_multiprocess_config(
        mode_value=viewmodel.execution_mode,
        worker_count_value=viewmodel.worker_count,
        max_inflight_chunks_value=viewmodel.max_inflight_chunks,
        ipc_queue_size_value=viewmodel.ipc_queue_size,
        retry_limit_value=viewmodel.retry_limit,
    )


def run_estimate(project: SchemaProject, viewmodel: RunCenterViewModel) -> RunCenterDiagnostics:
    profile = build_profile_from_viewmodel(viewmodel)
    validate_performance_profile(project, profile)
    estimates = estimate_workload(project, profile)
    return RunCenterDiagnostics(estimates=estimates, summary=summarize_estimates(estimates))


def run_build_partition_plan(
    project: SchemaProject,
    viewmodel: RunCenterViewModel,
) -> list[PartitionPlanEntry]:
    profile = build_profile_from_viewmodel(viewmodel)
    config = build_config_from_viewmodel(viewmodel)
    return build_partition_plan(project, profile, config)


def run_benchmark(
    project: SchemaProject,
    viewmodel: RunCenterViewModel,
    *,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> BenchmarkResult:
    profile = build_profile_from_viewmodel(viewmodel)
    return run_performance_benchmark(
        project,
        profile,
        on_event=on_event,
        cancel_requested=cancel_requested,
    )


def run_generation(
    project: SchemaProject,
    viewmodel: RunCenterViewModel,
    *,
    output_csv_folder: str | None = None,
    output_sqlite_path: str | None = None,
    on_event: Callable[[MultiprocessEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    fallback_to_single_process: bool = False,
) -> MultiprocessRunResult:
    profile = build_profile_from_viewmodel(viewmodel)
    config = build_config_from_viewmodel(viewmodel)
    return run_generation_with_multiprocessing(
        project,
        profile,
        config,
        output_csv_folder=output_csv_folder,
        output_sqlite_path=output_sqlite_path,
        on_event=on_event,
        cancel_requested=cancel_requested,
        fallback_to_single_process=fallback_to_single_process,
    )

