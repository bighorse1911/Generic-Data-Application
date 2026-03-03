from __future__ import annotations

import math

def _validation_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."

def _is_scalar_json_value(value: object) -> bool:
    return not isinstance(value, (dict, list))

def _scalar_identity(value: object) -> tuple[str, str]:
    return (type(value).__name__, repr(value))

def _parse_non_negative_int(
    value: object,
    *,
    location: str,
    field_name: str,
    hint: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be an integer",
                hint,
            )
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be an integer",
                hint,
            )
        ) from exc
    if parsed < 0:
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} cannot be negative",
                hint,
            )
        )
    return parsed

def _parse_probability(
    value: object,
    *,
    location: str,
    field_name: str,
    hint: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be numeric",
                hint,
            )
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be numeric",
                hint,
            )
        ) from exc
    if (not math.isfinite(parsed)) or parsed < 0.0 or parsed > 1.0:
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be between 0 and 1",
                hint,
            )
        )
    return parsed

def _parse_non_negative_finite_float(
    value: object,
    *,
    location: str,
    field_name: str,
    hint: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be numeric",
                hint,
            )
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be numeric",
                hint,
            )
        ) from exc
    if (not math.isfinite(parsed)) or parsed < 0.0:
        raise ValueError(
            _validation_error(
                location,
                f"{field_name} must be a finite value >= 0",
                hint,
            )
        )
    return parsed


__all__ = [
    "_validation_error",
    "_is_scalar_json_value",
    "_scalar_identity",
    "_parse_non_negative_int",
    "_parse_probability",
    "_parse_non_negative_finite_float",
]
