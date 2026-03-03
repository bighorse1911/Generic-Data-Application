from __future__ import annotations

from dataclasses import dataclass, field

OUTPUT_MODES: tuple[str, ...] = ("preview", "csv", "sqlite", "all")

FK_CACHE_MODES: tuple[str, ...] = ("auto", "memory", "disk_spill")

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
