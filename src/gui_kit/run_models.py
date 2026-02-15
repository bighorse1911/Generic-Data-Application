from __future__ import annotations

from dataclasses import dataclass

from src.multiprocessing_runtime import EXECUTION_MODES
from src.performance_scaling import FK_CACHE_MODES
from src.performance_scaling import OUTPUT_MODES

__all__ = [
    "RunWorkflowViewModel",
    "coerce_execution_mode",
    "coerce_output_mode",
]


@dataclass
class RunWorkflowViewModel:
    """Superset run-workflow UI model shared across run surfaces."""

    schema_path: str = ""
    target_tables: str = ""
    row_overrides_json: str = ""
    preview_row_target: str = "500"
    output_mode: str = OUTPUT_MODES[0]
    chunk_size_rows: str = "10000"
    preview_page_size: str = "500"
    sqlite_batch_size: str = "5000"
    csv_buffer_rows: str = "5000"
    fk_cache_mode: str = FK_CACHE_MODES[0]
    strict_deterministic_chunking: bool = True

    execution_mode: str = EXECUTION_MODES[0]
    worker_count: str = "1"
    max_inflight_chunks: str = "4"
    ipc_queue_size: str = "128"
    retry_limit: str = "1"

    profile_name: str = "default_v2_profile"



def coerce_output_mode(value: str) -> str:
    mode = str(value).strip().lower()
    return mode if mode in OUTPUT_MODES else OUTPUT_MODES[0]



def coerce_execution_mode(value: str) -> str:
    mode = str(value).strip().lower()
    return mode if mode in EXECUTION_MODES else EXECUTION_MODES[0]
