"""Data-quality profile (DG06) shared helper functions."""

from __future__ import annotations

import random


def _profile_rate_triggered(rng: random.Random, rate: float) -> bool:
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return rng.random() < rate


def _profile_clamp_probability(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _profile_scalar_identity(value: object) -> tuple[str, str]:
    return (type(value).__name__, repr(value))


def _profile_matches_where(
    row: dict[str, object],
    where_predicates: list[tuple[str, set[tuple[str, str]]]],
) -> bool:
    for column_name, allowed_values in where_predicates:
        marker = _profile_scalar_identity(row.get(column_name))
        if marker not in allowed_values:
            return False
    return True


def _default_format_error_value(
    *,
    dtype: str,
    profile_id: str,
) -> str:
    if dtype == "date":
        return f"INVALID_DATE_{profile_id}"
    if dtype == "datetime":
        return f"INVALID_DATETIME_{profile_id}"
    if dtype in {"int", "float", "decimal"}:
        return f"INVALID_NUMERIC_{profile_id}"
    if dtype == "bool":
        return f"INVALID_BOOL_{profile_id}"
    return f"INVALID_FORMAT_{profile_id}"


__all__ = [
    "_profile_rate_triggered",
    "_profile_clamp_probability",
    "_profile_scalar_identity",
    "_profile_matches_where",
    "_default_format_error_value",
]
