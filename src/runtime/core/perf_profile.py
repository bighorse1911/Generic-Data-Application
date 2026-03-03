from __future__ import annotations

import json
from typing import Any

from src.runtime.core.perf_types import FK_CACHE_MODES, OUTPUT_MODES, PerformanceProfile

def _performance_error(field: str, issue: str, hint: str) -> str:
    return f"Performance Workbench / {field}: {issue}. Fix: {hint}."

def _parse_bounded_int(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
    hint: str,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_performance_error(field, "must be an integer", hint)) from exc
    if parsed < minimum:
        raise ValueError(_performance_error(field, f"value {parsed} must be >= {minimum}", hint))
    if parsed > maximum:
        raise ValueError(_performance_error(field, f"value {parsed} must be <= {maximum}", hint))
    return parsed

def _parse_output_mode(value: Any) -> str:
    text = str(value).strip().lower()
    if text not in OUTPUT_MODES:
        allowed = ", ".join(OUTPUT_MODES)
        raise ValueError(
            _performance_error(
                "Output mode",
                f"unsupported output mode '{value}'",
                f"choose one of: {allowed}",
            )
        )
    return text

def _parse_fk_cache_mode(value: Any) -> str:
    text = str(value).strip().lower()
    if text not in FK_CACHE_MODES:
        allowed = ", ".join(FK_CACHE_MODES)
        raise ValueError(
            _performance_error(
                "FK cache mode",
                f"unsupported FK cache mode '{value}'",
                f"choose one of: {allowed}",
            )
        )
    return text

def _parse_strict_deterministic_chunking(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    raise ValueError(
        _performance_error(
            "Strict deterministic chunking",
            "must be true or false",
            "set strict deterministic chunking to true or false",
        )
    )

def _parse_target_tables(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if text == "":
        return ()
    parts = [part.strip() for part in text.split(",") if part.strip() != ""]
    if len(parts) != len(set(parts)):
        raise ValueError(
            _performance_error(
                "Target tables",
                "contains duplicate table names",
                "list each table name once, separated by commas",
            )
        )
    return tuple(parts)

def _parse_row_overrides_json(value: Any) -> dict[str, int]:
    if value is None:
        return {}
    text = str(value).strip()
    if text == "":
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            _performance_error(
                "Row overrides JSON",
                f"invalid JSON at line {exc.lineno}, column {exc.colno}",
                "enter JSON object like {\"orders\": 250000}",
            )
        ) from exc
    if not isinstance(decoded, dict):
        raise ValueError(
            _performance_error(
                "Row overrides JSON",
                "must be a JSON object",
                "enter JSON object mapping table name to positive integer row count",
            )
        )
    out: dict[str, int] = {}
    for raw_name, raw_rows in decoded.items():
        if not isinstance(raw_name, str) or raw_name.strip() == "":
            raise ValueError(
                _performance_error(
                    "Row overrides JSON",
                    "contains an empty table name key",
                    "use non-empty string keys for table names",
                )
            )
        clean_name = raw_name.strip()
        out[clean_name] = _parse_bounded_int(
            raw_rows,
            field=f"Row override / {clean_name}",
            minimum=1,
            maximum=10_000_000,
            hint="set a positive whole-number row count <= 10000000",
        )
    return out

def build_performance_profile(
    *,
    target_tables_value: Any,
    row_overrides_json_value: Any,
    preview_row_target_value: Any,
    output_mode_value: Any,
    chunk_size_rows_value: Any,
    preview_page_size_value: Any,
    sqlite_batch_size_value: Any,
    csv_buffer_rows_value: Any,
    fk_cache_mode_value: Any,
    strict_deterministic_chunking_value: Any,
) -> PerformanceProfile:
    return PerformanceProfile(
        target_tables=_parse_target_tables(target_tables_value),
        row_overrides=_parse_row_overrides_json(row_overrides_json_value),
        preview_row_target=_parse_bounded_int(
            preview_row_target_value,
            field="Preview row target",
            minimum=1,
            maximum=200_000,
            hint="set a positive whole number <= 200000",
        ),
        output_mode=_parse_output_mode(output_mode_value),
        chunk_size_rows=_parse_bounded_int(
            chunk_size_rows_value,
            field="Chunk size rows",
            minimum=1,
            maximum=1_000_000,
            hint="set a positive whole number <= 1000000",
        ),
        preview_page_size=_parse_bounded_int(
            preview_page_size_value,
            field="Preview page size",
            minimum=1,
            maximum=20_000,
            hint="set a positive whole number <= 20000",
        ),
        sqlite_batch_size=_parse_bounded_int(
            sqlite_batch_size_value,
            field="SQLite batch size",
            minimum=1,
            maximum=1_000_000,
            hint="set a positive whole number <= 1000000",
        ),
        csv_buffer_rows=_parse_bounded_int(
            csv_buffer_rows_value,
            field="CSV buffer rows",
            minimum=1,
            maximum=1_000_000,
            hint="set a positive whole number <= 1000000",
        ),
        fk_cache_mode=_parse_fk_cache_mode(fk_cache_mode_value),
        strict_deterministic_chunking=_parse_strict_deterministic_chunking(
            strict_deterministic_chunking_value
        ),
    )
