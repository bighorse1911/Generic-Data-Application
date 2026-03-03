from __future__ import annotations

import math

from src.schema.validators.common import _validation_error


def _parse_float_param(
    params: dict[str, object],
    key: str,
    *,
    location: str,
    hint: str,
    default: float | None = None,
    required: bool = False,
) -> float | None:
    raw: object | None
    if key in params:
        raw = params.get(key)
    else:
        raw = default
    if raw is None:
        if required:
            raise ValueError(
                f"{location}: params.{key} is required. "
                f"Fix: {hint}."
            )
        return None
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{location}: params.{key} must be numeric. "
            f"Fix: {hint}."
        ) from exc

def _parse_int_param(
    params: dict[str, object],
    key: str,
    *,
    location: str,
    hint: str,
    default: int | None = None,
    required: bool = False,
) -> int | None:
    raw: object | None
    if key in params:
        raw = params.get(key)
    else:
        raw = default
    if raw is None:
        if required:
            raise ValueError(
                f"{location}: params.{key} is required. "
                f"Fix: {hint}."
            )
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{location}: params.{key} must be an integer. "
            f"Fix: {hint}."
        ) from exc

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
"_parse_float_param",
"_parse_int_param",
"_parse_non_negative_int",
"_parse_probability",
"_parse_non_negative_finite_float",
]
