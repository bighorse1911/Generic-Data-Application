from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict

from src.generation.generator_common import _generator_error, _parse_offset_bounds
from src.generation.registry_core import GenContext, register


@register("date")
def gen_date(params: Dict[str, Any], ctx: GenContext) -> str:
    start_s = params.get("start", "2000-01-01")
    end_s = params.get("end", "2026-12-31")
    start = date.fromisoformat(start_s)
    end = date.fromisoformat(end_s)
    if end < start:
        raise ValueError(
            _generator_error(
                "Generator 'date'",
                "params.end is earlier than params.start",
                "set params.end >= params.start",
            )
        )
    days = (end - start).days
    d = start + timedelta(days=ctx.rng.randint(0, days))
    return d.isoformat()


@register("timestamp_utc")
def gen_timestamp_utc(params: Dict[str, Any], ctx: GenContext) -> str:
    def parse(s: str) -> datetime:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    start = parse(params.get("start", "2000-01-01T00:00:00Z"))
    end = parse(params.get("end", "2026-12-31T23:59:59Z"))
    if end < start:
        raise ValueError(
            _generator_error(
                "Generator 'timestamp_utc'",
                "params.end is earlier than params.start",
                "set params.end >= params.start",
            )
        )

    span = int((end - start).total_seconds())
    dt = start + timedelta(seconds=ctx.rng.randint(0, span))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@register("time_offset")
def gen_time_offset(params: Dict[str, Any], ctx: GenContext) -> str:
    location = f"Table '{ctx.table}', generator 'time_offset'"
    base_col = params.get("base_column")
    if not isinstance(base_col, str) or base_col.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                "params.base_column is required",
                "set params.base_column to a source date/datetime column name and add it to depends_on",
            )
        )
    base_col = base_col.strip()

    if base_col not in ctx.row:
        raise ValueError(
            _generator_error(
                location,
                f"base_column '{base_col}' is not available in row context",
                "set depends_on to include the source column so it generates first",
            )
        )

    direction = params.get("direction", "after")
    if not isinstance(direction, str) or direction not in {"after", "before"}:
        raise ValueError(
            _generator_error(
                location,
                f"unsupported direction '{direction}'",
                "use direction 'after' or 'before'",
            )
        )
    sign = 1 if direction == "after" else -1

    base_value = ctx.row[base_col]
    if not isinstance(base_value, str) or base_value.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                f"base_column '{base_col}' must contain an ISO date/datetime string",
                "generate the source column as date/datetime before applying time_offset",
            )
        )

    base_text = base_value.strip()
    uses_days = ("min_days" in params) or ("max_days" in params)
    uses_seconds = ("min_seconds" in params) or ("max_seconds" in params)

    if uses_days and uses_seconds:
        raise ValueError(
            _generator_error(
                location,
                "cannot mix day and second offsets in one config",
                "use min_days/max_days for date values or min_seconds/max_seconds for datetime values",
            )
        )

    if uses_days or "T" not in base_text:
        try:
            base_date = date.fromisoformat(base_text)
        except ValueError as exc:
            raise ValueError(
                _generator_error(
                    location,
                    f"base value '{base_text}' is not a valid ISO date",
                    "set base_column to a date value like YYYY-MM-DD",
                )
            ) from exc
        min_days, max_days = _parse_offset_bounds(
            params,
            min_key="min_days",
            max_key="max_days",
            location=location,
            unit_label="day",
        )
        days = ctx.rng.randint(min_days, max_days)
        return (base_date + timedelta(days=sign * days)).isoformat()

    base_dt_text = base_text.replace("Z", "+00:00")
    try:
        base_dt = datetime.fromisoformat(base_dt_text)
    except ValueError as exc:
        raise ValueError(
            _generator_error(
                location,
                f"base value '{base_text}' is not a valid ISO datetime",
                "set base_column to a datetime value like 2026-01-01T00:00:00Z",
            )
        ) from exc

    min_seconds, max_seconds = _parse_offset_bounds(
        params,
        min_key="min_seconds",
        max_key="max_seconds",
        location=location,
        unit_label="second",
    )
    seconds = ctx.rng.randint(min_seconds, max_seconds)
    out_dt = base_dt + timedelta(seconds=sign * seconds)
    if out_dt.tzinfo is None:
        return out_dt.isoformat()
    return out_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["gen_date", "gen_time_offset", "gen_timestamp_utc"]
