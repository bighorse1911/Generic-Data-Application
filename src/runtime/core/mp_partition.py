from __future__ import annotations

import hashlib
import time
from dataclasses import replace

from src.performance_scaling import PerformanceProfile, build_chunk_plan, validate_performance_profile
from src.schema_project_model import SchemaProject
from src.runtime.core.mp_config import _orchestrator_error, validate_multiprocess_config
from src.runtime.core.mp_types import MultiprocessConfig, PartitionPlanEntry, WorkerStatus

def _topological_selected_table_order(
    project: SchemaProject,
    selected_tables: set[str],
) -> tuple[str, ...]:
    parents_by_child: dict[str, set[str]] = {name: set() for name in selected_tables}
    children_by_parent: dict[str, set[str]] = {name: set() for name in selected_tables}

    for fk in project.foreign_keys:
        if fk.parent_table not in selected_tables or fk.child_table not in selected_tables:
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
            _orchestrator_error(
                "Partition plan",
                f"detected cyclic table dependencies ({unresolved_text})",
                "remove cyclic FK dependencies or choose an acyclic table subset",
            )
        )

    return tuple(ordered)

def _selected_tables_with_required_parents(
    project: SchemaProject,
    profile: PerformanceProfile,
) -> tuple[str, ...]:
    selected = set(profile.target_tables or tuple(table.table_name for table in project.tables))
    parent_by_child: dict[str, set[str]] = {}
    for fk in project.foreign_keys:
        parent_by_child.setdefault(fk.child_table, set()).add(fk.parent_table)

    changed = True
    while changed:
        changed = False
        for table_name in list(selected):
            for parent_name in parent_by_child.get(table_name, set()):
                if parent_name not in selected:
                    selected.add(parent_name)
                    changed = True

    return _topological_selected_table_order(project, selected)

def build_partition_plan(
    project: SchemaProject,
    profile: PerformanceProfile,
    config: MultiprocessConfig,
) -> list[PartitionPlanEntry]:
    validate_performance_profile(project, profile)
    validate_multiprocess_config(config)

    selected_with_parents = _selected_tables_with_required_parents(project, profile)
    effective_profile = replace(profile, target_tables=selected_with_parents)

    chunk_entries = build_chunk_plan(project, effective_profile)
    worker_count = 1 if config.mode == "single_process" else config.worker_count

    out: list[PartitionPlanEntry] = []
    for idx, chunk in enumerate(chunk_entries, start=1):
        partition_id = f"{chunk.table_name}|stage={chunk.stage}|chunk={chunk.chunk_index}"
        assigned_worker = ((idx - 1) % worker_count) + 1
        out.append(
            PartitionPlanEntry(
                partition_id=partition_id,
                table_name=chunk.table_name,
                stage=chunk.stage,
                chunk_index=chunk.chunk_index,
                start_row=chunk.start_row,
                end_row=chunk.end_row,
                rows_in_partition=chunk.rows_in_chunk,
                assigned_worker=assigned_worker,
            )
        )
    return out

def build_worker_status_snapshot(config: MultiprocessConfig) -> dict[int, WorkerStatus]:
    worker_count = 1 if config.mode == "single_process" else config.worker_count
    now = time.time()
    return {
        worker_id: WorkerStatus(
            worker_id=worker_id,
            last_heartbeat_epoch=now,
        )
        for worker_id in range(1, worker_count + 1)
    }

def derive_partition_seed(project_seed: int, table_name: str, partition_id: str) -> int:
    digest = hashlib.sha256(f"{project_seed}:{table_name}:{partition_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)
