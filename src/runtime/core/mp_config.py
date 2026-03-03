from __future__ import annotations

import os
from typing import Any

from src.runtime.core.mp_types import EXECUTION_MODES, MultiprocessConfig

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
