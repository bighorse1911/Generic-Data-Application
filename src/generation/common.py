"""Shared generation utility helpers."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

def _runtime_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _stable_subseed(base_seed: int, name: str) -> int:
    """
    Deterministically derive a per-table/per-feature seed from base_seed and a string name.
    Avoids Python's built-in hash() which is randomized between runs.
    """
    h = hashlib.sha256(f"{base_seed}:{name}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _iso_date(d: date) -> str:
    return d.isoformat()


def _iso_datetime(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse_iso_date_value(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("not a date string")
    return date.fromisoformat(value.strip())


def _parse_iso_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip() != "":
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("not a datetime string")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


__all__ = ["_runtime_error", "_stable_subseed", "_iso_date", "_iso_datetime", "_parse_iso_date_value", "_parse_iso_datetime_value"]
