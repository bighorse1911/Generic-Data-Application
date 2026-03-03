from __future__ import annotations

import concurrent.futures
import random
import time
from typing import Callable

from src.performance_scaling import (
    PerformanceProfile,
    PerformanceRunCancelled,
    StrategyRunResult,
    run_generation_with_strategy,
    validate_performance_profile,
)
from src.schema_project_model import SchemaProject
from src.runtime.core.mp_config import _orchestrator_error, validate_multiprocess_config
from src.runtime.core.mp_ledger import (
    apply_run_ledger_to_plan,
    create_run_ledger,
    save_run_ledger,
    validate_run_ledger,
)
from src.runtime.core.mp_partition import build_partition_plan, build_worker_status_snapshot, derive_partition_seed
from src.runtime.core.mp_types import (
    MultiprocessConfig,
    MultiprocessEvent,
    MultiprocessRunCancelled,
    MultiprocessRunResult,
    PartitionFailure,
    PartitionPlanEntry,
    WorkerStatus,
    _PartitionTask,
)

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
