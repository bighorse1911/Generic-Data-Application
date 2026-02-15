
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any
from typing import Callable

from src.performance_scaling import PerformanceProfile
from src.performance_scaling import PerformanceRunCancelled
from src.performance_scaling import StrategyRunResult
from src.performance_scaling import build_chunk_plan
from src.performance_scaling import run_generation_with_strategy
from src.performance_scaling import validate_performance_profile
from src.schema_project_model import SchemaProject

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


def _orchestrator_error(field: str, issue: str, hint: str) -> str:
    return f"Execution Orchestrator / {field}: {issue}. Fix: {hint}."


def _parse_mode(value: Any) -> str:
    text = str(value).strip().lower()
    if text not in EXECUTION_MODES:
        allowed = ", ".join(EXECUTION_MODES)
        raise ValueError(
            _orchestrator_error(
                "Execution mode",
                f"unsupported mode '{value}'",
                f"choose one of: {allowed}",
            )
        )
    return text


def _parse_bounded_int(value: Any, *, field: str, minimum: int, maximum: int, hint: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_orchestrator_error(field, "must be an integer", hint)) from exc
    if parsed < minimum:
        raise ValueError(_orchestrator_error(field, f"value {parsed} must be >= {minimum}", hint))
    if parsed > maximum:
        raise ValueError(_orchestrator_error(field, f"value {parsed} must be <= {maximum}", hint))
    return parsed


def build_multiprocess_config(
    *,
    mode_value: Any,
    worker_count_value: Any,
    max_inflight_chunks_value: Any,
    ipc_queue_size_value: Any,
    retry_limit_value: Any,
) -> MultiprocessConfig:
    mode = _parse_mode(mode_value)
    worker_count = _parse_bounded_int(
        worker_count_value,
        field="Worker count",
        minimum=1,
        maximum=256,
        hint="set worker_count to a positive whole number",
    )
    max_inflight_chunks = _parse_bounded_int(
        max_inflight_chunks_value,
        field="Max inflight chunks",
        minimum=1,
        maximum=4096,
        hint="set max_inflight_chunks to a positive whole number",
    )
    ipc_queue_size = _parse_bounded_int(
        ipc_queue_size_value,
        field="IPC queue size",
        minimum=1,
        maximum=100_000,
        hint="set ipc_queue_size to a positive whole number",
    )
    retry_limit = _parse_bounded_int(
        retry_limit_value,
        field="Retry limit",
        minimum=0,
        maximum=50,
        hint="set retry_limit to 0 or a positive whole number",
    )
    config = MultiprocessConfig(
        mode=mode,
        worker_count=worker_count,
        max_inflight_chunks=max_inflight_chunks,
        ipc_queue_size=ipc_queue_size,
        retry_limit=retry_limit,
    )
    validate_multiprocess_config(config)
    return config


def validate_multiprocess_config(config: MultiprocessConfig) -> None:
    cpu_count = max(1, int(os.cpu_count() or 1))

    if config.mode == "single_process" and config.worker_count != 1:
        raise ValueError(
            _orchestrator_error(
                "Worker count",
                "single_process mode requires worker_count=1",
                "set worker_count to 1, or choose mode='multi_process_local'",
            )
        )

    if config.mode == "multi_process_local" and config.worker_count > cpu_count:
        raise ValueError(
            _orchestrator_error(
                "Worker count",
                f"value {config.worker_count} exceeds available CPU count {cpu_count}",
                f"set worker_count between 1 and {cpu_count}",
            )
        )

    if config.max_inflight_chunks < config.worker_count:
        raise ValueError(
            _orchestrator_error(
                "Max inflight chunks",
                (
                    f"value {config.max_inflight_chunks} is lower than worker_count={config.worker_count} "
                    "and can starve workers"
                ),
                "set max_inflight_chunks >= worker_count",
            )
        )

    if config.ipc_queue_size < config.max_inflight_chunks:
        raise ValueError(
            _orchestrator_error(
                "IPC queue size",
                (
                    f"value {config.ipc_queue_size} is lower than max_inflight_chunks={config.max_inflight_chunks}"
                ),
                "set ipc_queue_size >= max_inflight_chunks",
            )
        )


def multiprocess_config_to_payload(config: MultiprocessConfig) -> dict[str, object]:
    return {
        "mode": config.mode,
        "worker_count": config.worker_count,
        "max_inflight_chunks": config.max_inflight_chunks,
        "ipc_queue_size": config.ipc_queue_size,
        "retry_limit": config.retry_limit,
    }


def multiprocess_config_from_payload(payload: dict[str, object]) -> MultiprocessConfig:
    return build_multiprocess_config(
        mode_value=payload.get("mode", EXECUTION_MODES[0]),
        worker_count_value=payload.get("worker_count", 1),
        max_inflight_chunks_value=payload.get("max_inflight_chunks", 4),
        ipc_queue_size_value=payload.get("ipc_queue_size", 128),
        retry_limit_value=payload.get("retry_limit", 1),
    )


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


def create_run_ledger(
    project: SchemaProject,
    profile: PerformanceProfile,
    config: MultiprocessConfig,
    partition_plan: list[PartitionPlanEntry],
) -> dict[str, object]:
    selected_tables = _selected_tables_with_required_parents(project, profile)
    return {
        "project_name": project.name,
        "project_seed": project.seed,
        "mode": config.mode,
        "worker_count": config.worker_count,
        "selected_tables": list(selected_tables),
        "partitions": {
            entry.partition_id: {
                "table_name": entry.table_name,
                "stage": entry.stage,
                "chunk_index": entry.chunk_index,
                "status": entry.status,
                "retry_count": entry.retry_count,
                "error_message": entry.error_message,
            }
            for entry in partition_plan
        },
    }


def save_run_ledger(path_value: str, ledger: dict[str, object]) -> Path:
    path_text = str(path_value).strip()
    if path_text == "":
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                "output path is required",
                "choose a writable JSON file path",
            )
        )
    path = Path(path_text)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                f"could not write ledger file ({exc})",
                "choose a writable output path",
            )
        ) from exc
    return path


def load_run_ledger(path_value: str) -> dict[str, object]:
    path_text = str(path_value).strip()
    if path_text == "":
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                "path is required",
                "choose an existing ledger JSON file",
            )
        )
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                f"ledger file '{path_text}' does not exist",
                "choose an existing ledger JSON file",
            )
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                f"failed to read ledger JSON ({exc})",
                "choose a valid JSON ledger file",
            )
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                "ledger JSON must be an object",
                "store ledger metadata and partitions in a JSON object",
            )
        )
    partitions = payload.get("partitions")
    if not isinstance(partitions, dict):
        raise ValueError(
            _orchestrator_error(
                "Run ledger",
                "ledger JSON is missing object field 'partitions'",
                "include a partitions object keyed by partition_id",
            )
        )
    return payload


def validate_run_ledger(
    project: SchemaProject,
    profile: PerformanceProfile,
    config: MultiprocessConfig,
    ledger: dict[str, object],
) -> None:
    ledger_name = ledger.get("project_name")
    ledger_seed = ledger.get("project_seed")
    ledger_mode = ledger.get("mode")
    ledger_selected = ledger.get("selected_tables")

    selected_tables = list(_selected_tables_with_required_parents(project, profile))

    if ledger_name != project.name or ledger_seed != project.seed:
        raise ValueError(
            _orchestrator_error(
                "Run recovery",
                "ledger project metadata does not match current schema",
                "load the schema used to create this ledger, or start a fresh run",
            )
        )

    if ledger_mode != config.mode:
        raise ValueError(
            _orchestrator_error(
                "Run recovery",
                f"ledger mode '{ledger_mode}' does not match current mode '{config.mode}'",
                "use the same execution mode as the saved ledger",
            )
        )

    if list(ledger_selected or []) != selected_tables:
        raise ValueError(
            _orchestrator_error(
                "Run recovery",
                "ledger selected tables do not match current profile",
                "use the same target tables/profile as the saved ledger",
            )
        )


def apply_run_ledger_to_plan(
    partition_plan: list[PartitionPlanEntry],
    ledger: dict[str, object],
) -> None:
    partitions = ledger.get("partitions")
    if not isinstance(partitions, dict):
        return

    for entry in partition_plan:
        raw = partitions.get(entry.partition_id)
        if not isinstance(raw, dict):
            continue
        status = raw.get("status")
        if isinstance(status, str) and status.strip() != "":
            entry.status = status.strip()
        retry_count = raw.get("retry_count")
        if isinstance(retry_count, int) and retry_count >= 0:
            entry.retry_count = retry_count
        error_message = raw.get("error_message")
        if isinstance(error_message, str):
            entry.error_message = error_message


def _emit_event(on_event: Callable[[MultiprocessEvent], None] | None, event: MultiprocessEvent) -> None:
    if on_event is None:
        return
    on_event(event)


def _ensure_not_cancelled(cancel_requested: Callable[[], bool] | None, phase: str) -> None:
    if cancel_requested is None:
        return
    if cancel_requested():
        raise MultiprocessRunCancelled(
            _orchestrator_error(
                "Cancel",
                f"run was cancelled during {phase}",
                "restart execution when ready",
            )
        )


def _run_partition_task(task: _PartitionTask) -> dict[str, object]:
    if task.force_fail:
        raise RuntimeError(f"injected worker failure for partition '{task.partition_id}'")

    row_count = max(0, (task.end_row - task.start_row) + 1)
    rng = random.Random(task.partition_seed)

    checksum = 0
    for offset in range(row_count):
        value = int(rng.random() * 1_000_000)
        checksum = (checksum + value + offset + task.start_row) % 2_147_483_647

    memory_mb = round((row_count * 24.0) / (1024.0 * 1024.0), 6)
    return {
        "partition_id": task.partition_id,
        "table_name": task.table_name,
        "rows_processed": row_count,
        "checksum": checksum,
        "memory_mb": memory_mb,
    }


def _group_by_stage(partition_plan: list[PartitionPlanEntry]) -> dict[int, list[PartitionPlanEntry]]:
    by_stage: dict[int, list[PartitionPlanEntry]] = {}
    for entry in partition_plan:
        by_stage.setdefault(entry.stage, []).append(entry)
    for stage_entries in by_stage.values():
        stage_entries.sort(key=lambda item: (item.table_name, item.chunk_index))
    return by_stage


def _update_ledger_partition(ledger: dict[str, object], entry: PartitionPlanEntry) -> None:
    partitions = ledger.setdefault("partitions", {})
    if not isinstance(partitions, dict):
        return
    part = partitions.setdefault(entry.partition_id, {})
    if not isinstance(part, dict):
        return
    part["table_name"] = entry.table_name
    part["stage"] = entry.stage
    part["chunk_index"] = entry.chunk_index
    part["status"] = entry.status
    part["retry_count"] = entry.retry_count
    part["error_message"] = entry.error_message


def _persist_ledger_if_needed(run_ledger_path: str | None, ledger: dict[str, object]) -> None:
    if run_ledger_path is None or str(run_ledger_path).strip() == "":
        return
    save_run_ledger(run_ledger_path, ledger)


def _run_single_process_strategy(
    project: SchemaProject,
    profile: PerformanceProfile,
    *,
    output_csv_folder: str | None,
    output_sqlite_path: str | None,
    cancel_requested: Callable[[], bool] | None,
) -> StrategyRunResult:
    try:
        return run_generation_with_strategy(
            project,
            profile,
            output_csv_folder=output_csv_folder,
            output_sqlite_path=output_sqlite_path,
            cancel_requested=cancel_requested,
        )
    except PerformanceRunCancelled as exc:
        raise MultiprocessRunCancelled(str(exc)) from exc


def run_generation_with_multiprocessing(
    project: SchemaProject,
    profile: PerformanceProfile,
    config: MultiprocessConfig,
    *,
    output_csv_folder: str | None = None,
    output_sqlite_path: str | None = None,
    on_event: Callable[[MultiprocessEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    fallback_to_single_process: bool = False,
    run_ledger: dict[str, object] | None = None,
    run_ledger_path: str | None = None,
    fail_partition_ids: set[str] | None = None,
) -> MultiprocessRunResult:
    validate_performance_profile(project, profile)
    validate_multiprocess_config(config)

    partition_plan = build_partition_plan(project, profile, config)
    worker_status = build_worker_status_snapshot(config)
    failures: list[PartitionFailure] = []
    total_rows = sum(entry.rows_in_partition for entry in partition_plan)

    if run_ledger is None:
        ledger = create_run_ledger(project, profile, config, partition_plan)
    else:
        validate_run_ledger(project, profile, config, run_ledger)
        ledger = run_ledger
        apply_run_ledger_to_plan(partition_plan, ledger)

    _persist_ledger_if_needed(run_ledger_path, ledger)
    _emit_event(
        on_event,
        MultiprocessEvent(
            kind="started",
            total_rows=total_rows,
            message="Multiprocessing run started.",
        ),
    )

    processed_rows = 0
    for entry in partition_plan:
        if entry.status == "done":
            processed_rows += entry.rows_in_partition

    if config.mode == "single_process":
        for entry in partition_plan:
            if entry.status == "done":
                continue
            _ensure_not_cancelled(cancel_requested, "single-process partition sweep")
            entry.status = "done"
            _update_ledger_partition(ledger, entry)
            _persist_ledger_if_needed(run_ledger_path, ledger)
            processed_rows += entry.rows_in_partition
            _emit_event(
                on_event,
                MultiprocessEvent(
                    kind="progress",
                    partition_id=entry.partition_id,
                    table_name=entry.table_name,
                    worker_id=1,
                    rows_processed=processed_rows,
                    total_rows=total_rows,
                    message="Single-process partition progress.",
                ),
            )

        strategy_result = _run_single_process_strategy(
            project,
            profile,
            output_csv_folder=output_csv_folder,
            output_sqlite_path=output_sqlite_path,
            cancel_requested=cancel_requested,
        )
        _emit_event(
            on_event,
            MultiprocessEvent(
                kind="run_done",
                rows_processed=strategy_result.total_rows,
                total_rows=strategy_result.total_rows,
                message="Single-process run complete.",
            ),
        )
        return MultiprocessRunResult(
            mode=config.mode,
            fallback_used=False,
            partition_plan=partition_plan,
            worker_status=worker_status,
            failures=failures,
            strategy_result=strategy_result,
            total_rows=strategy_result.total_rows,
            run_ledger=ledger,
        )

    forced_failures = set(fail_partition_ids or set())
    stage_groups = _group_by_stage(partition_plan)

    def fallback_strategy(reason: str) -> MultiprocessRunResult:
        for status in worker_status.values():
            status.state = "fallback"
            status.last_heartbeat_epoch = time.time()
        _emit_event(
            on_event,
            MultiprocessEvent(
                kind="fallback",
                message=reason,
                rows_processed=processed_rows,
                total_rows=total_rows,
            ),
        )
        strategy_result = _run_single_process_strategy(
            project,
            profile,
            output_csv_folder=output_csv_folder,
            output_sqlite_path=output_sqlite_path,
            cancel_requested=cancel_requested,
        )
        _emit_event(
            on_event,
            MultiprocessEvent(
                kind="run_done",
                rows_processed=strategy_result.total_rows,
                total_rows=strategy_result.total_rows,
                message="Fallback single-process run complete.",
            ),
        )
        return MultiprocessRunResult(
            mode=config.mode,
            fallback_used=True,
            partition_plan=partition_plan,
            worker_status=worker_status,
            failures=failures,
            strategy_result=strategy_result,
            total_rows=strategy_result.total_rows,
            run_ledger=ledger,
        )

    try:
        for stage in sorted(stage_groups):
            stage_entries = [entry for entry in stage_groups[stage] if entry.status != "done"]
            if not stage_entries:
                continue

            pending = list(stage_entries)
            inflight: dict[concurrent.futures.Future[dict[str, object]], PartitionPlanEntry] = {}

            with concurrent.futures.ProcessPoolExecutor(max_workers=config.worker_count) as executor:
                while pending or inflight:
                    _ensure_not_cancelled(cancel_requested, f"stage {stage} execution")

                    while pending and len(inflight) < config.max_inflight_chunks:
                        entry = pending.pop(0)
                        worker = worker_status[entry.assigned_worker]
                        worker.state = "running"
                        worker.current_table = entry.table_name
                        worker.current_partition_id = entry.partition_id
                        worker.last_heartbeat_epoch = time.time()

                        task = _PartitionTask(
                            partition_id=entry.partition_id,
                            table_name=entry.table_name,
                            start_row=entry.start_row,
                            end_row=entry.end_row,
                            partition_seed=derive_partition_seed(
                                project.seed,
                                entry.table_name,
                                entry.partition_id,
                            ),
                            force_fail=(
                                entry.partition_id in forced_failures and entry.retry_count == 0
                            ),
                        )
                        entry.status = "running"
                        _update_ledger_partition(ledger, entry)
                        _persist_ledger_if_needed(run_ledger_path, ledger)
                        future = executor.submit(_run_partition_task, task)
                        inflight[future] = entry

                    if not inflight:
                        continue

                    done, _ = concurrent.futures.wait(
                        tuple(inflight.keys()),
                        timeout=0.2,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    if not done:
                        now = time.time()
                        for worker in worker_status.values():
                            if worker.state == "running":
                                worker.last_heartbeat_epoch = now
                        continue

                    for future in done:
                        entry = inflight.pop(future)
                        worker = worker_status[entry.assigned_worker]
                        worker.last_heartbeat_epoch = time.time()

                        try:
                            result = future.result()
                        except Exception as exc:
                            entry.error_message = str(exc)
                            entry.retry_count += 1
                            retry_action = "retry" if entry.retry_count <= config.retry_limit else "failed"
                            failures.append(
                                PartitionFailure(
                                    partition_id=entry.partition_id,
                                    error=str(exc),
                                    retry_count=entry.retry_count,
                                    action=retry_action,
                                )
                            )

                            if entry.retry_count <= config.retry_limit:
                                entry.status = "pending"
                                worker.state = "retrying"
                                _update_ledger_partition(ledger, entry)
                                _persist_ledger_if_needed(run_ledger_path, ledger)
                                pending.append(entry)
                                _emit_event(
                                    on_event,
                                    MultiprocessEvent(
                                        kind="partition_failed",
                                        partition_id=entry.partition_id,
                                        table_name=entry.table_name,
                                        worker_id=entry.assigned_worker,
                                        rows_processed=processed_rows,
                                        total_rows=total_rows,
                                        retry_count=entry.retry_count,
                                        message=(
                                            f"Partition {entry.partition_id} failed and will be retried "
                                            f"({entry.retry_count}/{config.retry_limit})."
                                        ),
                                    ),
                                )
                                continue

                            entry.status = "failed"
                            worker.state = "failed"
                            _update_ledger_partition(ledger, entry)
                            _persist_ledger_if_needed(run_ledger_path, ledger)

                            raise ValueError(
                                _orchestrator_error(
                                    f"Partition {entry.partition_id}",
                                    f"worker execution failed ({exc})",
                                    (
                                        "review the failure panel, increase retry_limit, or use fallback "
                                        "to single_process mode"
                                    ),
                                )
                            ) from exc

                        rows_done = int(result.get("rows_processed", entry.rows_in_partition))
                        entry.status = "done"
                        entry.error_message = ""
                        processed_rows += rows_done

                        worker.state = "idle"
                        worker.current_table = ""
                        worker.current_partition_id = ""
                        worker.rows_processed += rows_done
                        worker.memory_mb = float(result.get("memory_mb", 0.0))
                        worker.throughput_rows_per_sec = float(rows_done)

                        _update_ledger_partition(ledger, entry)
                        _persist_ledger_if_needed(run_ledger_path, ledger)
                        _emit_event(
                            on_event,
                            MultiprocessEvent(
                                kind="progress",
                                partition_id=entry.partition_id,
                                table_name=entry.table_name,
                                worker_id=entry.assigned_worker,
                                rows_processed=processed_rows,
                                total_rows=total_rows,
                                message="Multiprocess partition progress.",
                            ),
                        )

    except MultiprocessRunCancelled:
        raise
    except ValueError as exc:
        if fallback_to_single_process:
            return fallback_strategy(str(exc))
        raise

    _ensure_not_cancelled(cancel_requested, "strategy generation")
    strategy_result = _run_single_process_strategy(
        project,
        profile,
        output_csv_folder=output_csv_folder,
        output_sqlite_path=output_sqlite_path,
        cancel_requested=cancel_requested,
    )

    _emit_event(
        on_event,
        MultiprocessEvent(
            kind="run_done",
            rows_processed=strategy_result.total_rows,
            total_rows=strategy_result.total_rows,
            message="Multiprocess run complete.",
        ),
    )

    return MultiprocessRunResult(
        mode=config.mode,
        fallback_used=False,
        partition_plan=partition_plan,
        worker_status=worker_status,
        failures=failures,
        strategy_result=strategy_result,
        total_rows=strategy_result.total_rows,
        run_ledger=ledger,
    )
