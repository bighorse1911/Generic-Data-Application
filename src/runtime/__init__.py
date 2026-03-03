"""Runtime package wrappers for performance and multiprocess execution."""

from importlib import import_module

_PERF_EXPORTS = {
    "OUTPUT_MODES",
    "FK_CACHE_MODES",
    "PerformanceProfile",
    "WorkloadEstimate",
    "WorkloadSummary",
    "ChunkPlanEntry",
    "ChunkPlanSummary",
    "RuntimeEvent",
    "BenchmarkResult",
    "StrategyRunResult",
    "PerformanceRunCancelled",
    "build_performance_profile",
    "validate_performance_profile",
    "build_chunk_plan",
    "estimate_workload",
    "summarize_estimates",
    "summarize_chunk_plan",
    "run_performance_benchmark",
    "run_generation_with_strategy",
}

_MP_EXPORTS = {
    "EXECUTION_MODES",
    "MultiprocessConfig",
    "PartitionPlanEntry",
    "WorkerStatus",
    "PartitionFailure",
    "MultiprocessEvent",
    "MultiprocessRunResult",
    "MultiprocessRunCancelled",
    "build_multiprocess_config",
    "validate_multiprocess_config",
    "multiprocess_config_to_payload",
    "multiprocess_config_from_payload",
    "build_partition_plan",
    "build_worker_status_snapshot",
    "derive_partition_seed",
    "create_run_ledger",
    "save_run_ledger",
    "load_run_ledger",
    "validate_run_ledger",
    "apply_run_ledger_to_plan",
    "run_generation_with_multiprocessing",
}

__all__ = sorted(_PERF_EXPORTS | _MP_EXPORTS)


def __getattr__(name: str):
    if name in _PERF_EXPORTS:
        module = import_module("src.runtime.performance")
        return getattr(module, name)
    if name in _MP_EXPORTS:
        module = import_module("src.runtime.multiprocessing")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
