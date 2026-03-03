from __future__ import annotations

from dataclasses import dataclass

EXECUTION_MODES: tuple[str, ...] = ("single_process", "multi_process_local")

@dataclass(frozen=True)
class MultiprocessConfig:
    mode: str = EXECUTION_MODES[0]
    worker_count: int = 1
    max_inflight_chunks: int = 4
    ipc_queue_size: int = 128
    retry_limit: int = 1

@dataclass
class PartitionPlanEntry:
    partition_id: str
    table_name: str
    stage: int
    chunk_index: int
    start_row: int
    end_row: int
    rows_in_partition: int
    assigned_worker: int
    status: str = "pending"
    retry_count: int = 0
    error_message: str = ""

@dataclass
class WorkerStatus:
    worker_id: int
    current_table: str = ""
    current_partition_id: str = ""
    rows_processed: int = 0
    throughput_rows_per_sec: float = 0.0
    memory_mb: float = 0.0
    last_heartbeat_epoch: float = 0.0
    state: str = "idle"

@dataclass(frozen=True)
class PartitionFailure:
    partition_id: str
    error: str
    retry_count: int
    action: str

@dataclass(frozen=True)
class MultiprocessEvent:
    kind: str
    message: str = ""
    partition_id: str | None = None
    table_name: str | None = None
    worker_id: int | None = None
    rows_processed: int = 0
    total_rows: int = 0
    retry_count: int = 0

@dataclass(frozen=True)
class MultiprocessRunResult:
    mode: str
    fallback_used: bool
    partition_plan: list[PartitionPlanEntry]
    worker_status: dict[int, WorkerStatus]
    failures: list[PartitionFailure]
    strategy_result: StrategyRunResult
    total_rows: int
    run_ledger: dict[str, object]

class MultiprocessRunCancelled(RuntimeError):
    pass

@dataclass(frozen=True)
class _PartitionTask:
    partition_id: str
    table_name: str
    start_row: int
    end_row: int
    partition_seed: int
    force_fail: bool = False
