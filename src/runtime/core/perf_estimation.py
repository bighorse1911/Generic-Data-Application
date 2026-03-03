from __future__ import annotations

from src.schema_project_model import SchemaProject
from src.runtime.core.perf_types import PerformanceProfile, WorkloadEstimate, WorkloadSummary

def _risk_priority(level: str) -> int:
    if level == "high":
        return 3
    if level == "medium":
        return 2
    return 1

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
