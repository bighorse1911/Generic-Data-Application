from __future__ import annotations

import json
from pathlib import Path

from src.performance_scaling import PerformanceProfile
from src.schema_project_model import SchemaProject
from src.runtime.core.mp_config import _orchestrator_error
from src.runtime.core.mp_partition import _selected_tables_with_required_parents
from src.runtime.core.mp_types import MultiprocessConfig, PartitionPlanEntry

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
