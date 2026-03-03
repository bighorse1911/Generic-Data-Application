from __future__ import annotations

from typing import Any

from src.schema_project_model import SchemaProject


def _erd_error(field: str, issue: str, hint: str) -> str:
    return f"ERD Designer / {field}: {issue}. Fix: {hint}."


ERD_AUTHORING_DTYPES: tuple[str, ...] = (
    "int",
    "decimal",
    "text",
    "bool",
    "date",
    "datetime",
    "bytes",
)


def _parse_non_empty_name(value: Any, *, field: str, hint: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(_erd_error(field, "value is required", hint))
    return value.strip()


def _parse_positive_int(value: Any, *, field: str, hint: str, allow_zero: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError(_erd_error(field, "must be an integer", hint))
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_erd_error(field, "must be an integer", hint)) from exc
    if allow_zero:
        if out < 0:
            raise ValueError(_erd_error(field, "must be >= 0", hint))
    elif out <= 0:
        raise ValueError(_erd_error(field, "must be > 0", hint))
    return out


def _parse_seed(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(
            _erd_error(
                "Schema seed",
                "must be an integer",
                "enter a whole-number seed value (for example 12345)",
            )
        )
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _erd_error(
                "Schema seed",
                "must be an integer",
                "enter a whole-number seed value (for example 12345)",
            )
        ) from exc


def _require_project(project: Any) -> SchemaProject:
    if isinstance(project, SchemaProject):
        return project
    raise ValueError(
        _erd_error(
            "Schema state",
            "schema project is not initialized",
            "create a new schema or load an existing schema before editing",
        )
    )


def _parse_authoring_dtype(
    dtype_value: Any,
    *,
    field: str,
) -> str:
    if not isinstance(dtype_value, str) or dtype_value.strip() == "":
        raise ValueError(
            _erd_error(
                field,
                "dtype is required",
                f"choose one of: {', '.join(ERD_AUTHORING_DTYPES)}",
            )
        )
    dtype = dtype_value.strip().lower()
    if dtype == "float":
        raise ValueError(
            _erd_error(
                field,
                "dtype 'float' is deprecated for new GUI columns",
                "choose dtype='decimal' for new numeric columns",
            )
        )
    if dtype not in ERD_AUTHORING_DTYPES:
        raise ValueError(
            _erd_error(
                field,
                f"unsupported dtype '{dtype}'",
                f"choose one of: {', '.join(ERD_AUTHORING_DTYPES)}",
            )
        )
    return dtype
