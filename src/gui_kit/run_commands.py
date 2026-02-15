from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.run_models import coerce_execution_mode
from src.gui_kit.run_models import coerce_output_mode
from src.multiprocessing_runtime import MultiprocessConfig
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunResult
from src.multiprocessing_runtime import PartitionPlanEntry
from src.multiprocessing_runtime import build_multiprocess_config
from src.multiprocessing_runtime import build_partition_plan
from src.multiprocessing_runtime import multiprocess_config_from_payload
from src.multiprocessing_runtime import multiprocess_config_to_payload
from src.multiprocessing_runtime import run_generation_with_multiprocessing
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import ChunkPlanEntry
from src.performance_scaling import PerformanceProfile
from src.performance_scaling import RuntimeEvent
from src.performance_scaling import StrategyRunResult
from src.performance_scaling import WorkloadEstimate
from src.performance_scaling import WorkloadSummary
from src.performance_scaling import build_chunk_plan
from src.performance_scaling import build_performance_profile
from src.performance_scaling import estimate_workload
from src.performance_scaling import run_generation_with_strategy
from src.performance_scaling import run_performance_benchmark
from src.performance_scaling import summarize_estimates
from src.performance_scaling import validate_performance_profile
from src.schema_project_model import SchemaProject

__all__ = [
    "RunWorkflowDiagnostics",
    "apply_execution_run_config_payload",
    "apply_performance_profile_payload",
    "apply_run_center_payload",
    "build_config_from_model",
    "build_profile_from_model",
    "execution_run_config_payload",
    "performance_profile_payload",
    "run_benchmark",
    "run_build_chunk_plan",
    "run_build_partition_plan",
    "run_estimate",
    "run_generation_multiprocess",
    "run_generation_strategy",
    "run_center_payload",
]


@dataclass(frozen=True)
class RunWorkflowDiagnostics:
    estimates: list[WorkloadEstimate]
    summary: WorkloadSummary



def build_profile_from_model(model: RunWorkflowViewModel) -> PerformanceProfile:
    return build_performance_profile(
        target_tables_value=model.target_tables,
        row_overrides_json_value=model.row_overrides_json,
        preview_row_target_value=model.preview_row_target,
        output_mode_value=model.output_mode,
        chunk_size_rows_value=model.chunk_size_rows,
        preview_page_size_value=model.preview_page_size,
        sqlite_batch_size_value=model.sqlite_batch_size,
        csv_buffer_rows_value=model.csv_buffer_rows,
        fk_cache_mode_value=model.fk_cache_mode,
        strict_deterministic_chunking_value=model.strict_deterministic_chunking,
    )



def build_config_from_model(model: RunWorkflowViewModel) -> MultiprocessConfig:
    return build_multiprocess_config(
        mode_value=model.execution_mode,
        worker_count_value=model.worker_count,
        max_inflight_chunks_value=model.max_inflight_chunks,
        ipc_queue_size_value=model.ipc_queue_size,
        retry_limit_value=model.retry_limit,
    )



def run_estimate(project: SchemaProject, model: RunWorkflowViewModel) -> RunWorkflowDiagnostics:
    profile = build_profile_from_model(model)
    validate_performance_profile(project, profile)
    estimates = estimate_workload(project, profile)
    return RunWorkflowDiagnostics(estimates=estimates, summary=summarize_estimates(estimates))



def run_build_chunk_plan(project: SchemaProject, model: RunWorkflowViewModel) -> list[ChunkPlanEntry]:
    profile = build_profile_from_model(model)
    validate_performance_profile(project, profile)
    return build_chunk_plan(project, profile)



def run_build_partition_plan(project: SchemaProject, model: RunWorkflowViewModel) -> list[PartitionPlanEntry]:
    profile = build_profile_from_model(model)
    config = build_config_from_model(model)
    return build_partition_plan(project, profile, config)



def run_benchmark(
    project: SchemaProject,
    model: RunWorkflowViewModel,
    *,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> BenchmarkResult:
    profile = build_profile_from_model(model)
    return run_performance_benchmark(
        project,
        profile,
        on_event=on_event,
        cancel_requested=cancel_requested,
    )



def run_generation_strategy(
    project: SchemaProject,
    model: RunWorkflowViewModel,
    *,
    output_csv_folder: str | None = None,
    output_sqlite_path: str | None = None,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> StrategyRunResult:
    profile = build_profile_from_model(model)
    return run_generation_with_strategy(
        project,
        profile,
        output_csv_folder=output_csv_folder,
        output_sqlite_path=output_sqlite_path,
        on_event=on_event,
        cancel_requested=cancel_requested,
    )



def run_generation_multiprocess(
    project: SchemaProject,
    model: RunWorkflowViewModel,
    *,
    output_csv_folder: str | None = None,
    output_sqlite_path: str | None = None,
    on_event: Callable[[MultiprocessEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    fallback_to_single_process: bool = False,
) -> MultiprocessRunResult:
    profile = build_profile_from_model(model)
    config = build_config_from_model(model)
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



def run_center_payload(model: RunWorkflowViewModel) -> dict[str, object]:
    return {
        "schema_path": model.schema_path,
        "target_tables": model.target_tables,
        "row_overrides_json": model.row_overrides_json,
        "preview_row_target": model.preview_row_target,
        "output_mode": model.output_mode,
        "chunk_size_rows": model.chunk_size_rows,
        "preview_page_size": model.preview_page_size,
        "sqlite_batch_size": model.sqlite_batch_size,
        "csv_buffer_rows": model.csv_buffer_rows,
        "fk_cache_mode": model.fk_cache_mode,
        "strict_deterministic_chunking": model.strict_deterministic_chunking,
        "execution_mode": model.execution_mode,
        "worker_count": model.worker_count,
        "max_inflight_chunks": model.max_inflight_chunks,
        "ipc_queue_size": model.ipc_queue_size,
        "retry_limit": model.retry_limit,
        "profile_name": model.profile_name,
    }



def apply_run_center_payload(model: RunWorkflowViewModel, payload: dict[str, object]) -> RunWorkflowViewModel:
    model.schema_path = str(payload.get("schema_path", ""))
    model.target_tables = str(payload.get("target_tables", ""))
    model.row_overrides_json = str(payload.get("row_overrides_json", ""))
    model.preview_row_target = str(payload.get("preview_row_target", "500"))
    model.output_mode = coerce_output_mode(str(payload.get("output_mode", model.output_mode)))
    model.chunk_size_rows = str(payload.get("chunk_size_rows", "10000"))
    model.preview_page_size = str(payload.get("preview_page_size", "500"))
    model.sqlite_batch_size = str(payload.get("sqlite_batch_size", "5000"))
    model.csv_buffer_rows = str(payload.get("csv_buffer_rows", "5000"))
    model.fk_cache_mode = str(payload.get("fk_cache_mode", model.fk_cache_mode))
    model.strict_deterministic_chunking = bool(payload.get("strict_deterministic_chunking", True))
    model.execution_mode = coerce_execution_mode(str(payload.get("execution_mode", model.execution_mode)))
    model.worker_count = str(payload.get("worker_count", "1"))
    model.max_inflight_chunks = str(payload.get("max_inflight_chunks", "4"))
    model.ipc_queue_size = str(payload.get("ipc_queue_size", "128"))
    model.retry_limit = str(payload.get("retry_limit", "1"))
    model.profile_name = str(payload.get("profile_name", model.profile_name or "default_v2_profile"))
    if model.profile_name.strip() == "":
        model.profile_name = "default_v2_profile"
    return model



def performance_profile_payload(profile: PerformanceProfile) -> dict[str, object]:
    return {
        "target_tables": list(profile.target_tables),
        "row_overrides": profile.row_overrides,
        "preview_row_target": profile.preview_row_target,
        "output_mode": profile.output_mode,
        "chunk_size_rows": profile.chunk_size_rows,
        "preview_page_size": profile.preview_page_size,
        "sqlite_batch_size": profile.sqlite_batch_size,
        "csv_buffer_rows": profile.csv_buffer_rows,
        "fk_cache_mode": profile.fk_cache_mode,
        "strict_deterministic_chunking": profile.strict_deterministic_chunking,
    }



def apply_performance_profile_payload(model: RunWorkflowViewModel, payload: dict[str, object]) -> RunWorkflowViewModel:
    target_tables = payload.get("target_tables", [])
    if isinstance(target_tables, list):
        model.target_tables = ", ".join(str(item).strip() for item in target_tables if str(item).strip() != "")
    else:
        model.target_tables = ""

    row_overrides = payload.get("row_overrides", {})
    if row_overrides in ({}, None):
        model.row_overrides_json = ""
    else:
        model.row_overrides_json = json.dumps(row_overrides, separators=(",", ":"))

    model.preview_row_target = str(payload.get("preview_row_target", 500))
    model.output_mode = coerce_output_mode(str(payload.get("output_mode", model.output_mode)))
    model.chunk_size_rows = str(payload.get("chunk_size_rows", 10000))
    model.preview_page_size = str(payload.get("preview_page_size", 500))
    model.sqlite_batch_size = str(payload.get("sqlite_batch_size", 5000))
    model.csv_buffer_rows = str(payload.get("csv_buffer_rows", 5000))
    model.fk_cache_mode = str(payload.get("fk_cache_mode", model.fk_cache_mode))
    model.strict_deterministic_chunking = bool(payload.get("strict_deterministic_chunking", True))
    return model



def execution_run_config_payload(model: RunWorkflowViewModel) -> dict[str, object]:
    profile = build_profile_from_model(model)
    config = build_config_from_model(model)
    return {
        "profile": performance_profile_payload(profile),
        "multiprocess": multiprocess_config_to_payload(config),
    }



def apply_execution_run_config_payload(model: RunWorkflowViewModel, payload: dict[str, object]) -> RunWorkflowViewModel:
    profile_payload = payload.get("profile", {})
    multiprocess_payload = payload.get("multiprocess", {})
    if not isinstance(profile_payload, dict) or not isinstance(multiprocess_payload, dict):
        raise ValueError(
            "Execution Orchestrator / Load run config: invalid config structure. "
            "Fix: include object fields 'profile' and 'multiprocess'."
        )

    apply_performance_profile_payload(model, profile_payload)

    config = multiprocess_config_from_payload(multiprocess_payload)
    model.execution_mode = config.mode
    model.worker_count = str(config.worker_count)
    model.max_inflight_chunks = str(config.max_inflight_chunks)
    model.ipc_queue_size = str(config.ipc_queue_size)
    model.retry_limit = str(config.retry_limit)
    return model
