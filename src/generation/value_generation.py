"""Per-column value generation helpers."""

from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta, timezone

from src.generators import GenContext, get_generator
from src.generation.common import _iso_date, _iso_datetime, _runtime_error
from src.schema_project_model import ColumnSpec

def _maybe_null(col, ctx: GenContext) -> bool:
    # PKs cannot be null
    if getattr(col, "primary_key", False):
        return False

    params = getattr(col, "params", None) or {}
    null_rate = params.get("null_rate", None)
    if null_rate is None:
        return False

    r = float(null_rate)
    if r <= 0.0:
        return False
    if r >= 1.0:
        return True
    return ctx.rng.random() < r


def _apply_numeric_post(col, v: object) -> object:
    if v is None:
        return None
    if not isinstance(v, (int, float)):
        return v

    params = getattr(col, "params", None) or {}
    mn = params.get("clamp_min", None)
    mx = params.get("clamp_max", None)

    x = float(v)
    if mn is not None:
        x = max(float(mn), x)
    if mx is not None:
        x = min(float(mx), x)

    # If dtype says int, keep int
    if getattr(col, "dtype", "") == "int":
        return int(round(x))

    if getattr(col, "dtype", "") == "decimal":
        scale = params.get("scale", None)
        if scale is not None:
            x = round(x, int(scale))
        return float(x)

    return x


def _gen_value(col: ColumnSpec, rng: random.Random, row_index: int, table_name: str, row: dict[str, object]) -> object:
    ctx = GenContext(
        row_index=row_index,
        table=table_name,
        row=row,
        rng=rng,
        column=col.name,
        dtype=col.dtype,
    )

    # Nulls (probabilistic)
    if _maybe_null(col, ctx):
        return None

    # Generate
    if getattr(col, "generator", None):
        try:
            fn = get_generator(col.generator)  # type: ignore[arg-type]
        except KeyError as exc:
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}', column '{col.name}'",
                    f"unknown generator '{col.generator}'",
                    "choose a registered generator name in column.generator",
                )
            ) from exc
        params = col.params or {}
        try:
            v = fn(params, ctx)
        except KeyError as exc:
            missing = str(exc.args[0]) if exc.args else "unknown"
            raise ValueError(
                f"Table '{table_name}', column '{col.name}': generator '{col.generator}' is missing required params key '{missing}'. "
                "Fix: set the required key in params before generation."
            ) from exc

        # Optional numeric outliers (only when numeric)
        out_rate = float(params.get("outlier_rate", 0.0) or 0.0)
        out_scale = float(params.get("outlier_scale", 3.0) or 3.0)
        if out_rate > 0 and isinstance(v, (int, float)) and rng.random() < out_rate:
            v = float(v) * out_scale

    else:
        v = _gen_value_fallback(col, rng, row_index)

    # Post-processing
    v = _apply_numeric_post(col, v)

    # choices override (if set)
    if col.choices:
        v = rng.choice(col.choices)

    # regex validation (if set)
    if col.pattern and v is not None:
        import re
        if not re.fullmatch(col.pattern, str(v)):
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}', column '{col.name}'",
                    f"value '{v}' does not match pattern '{col.pattern}'",
                    "adjust the generator output or update the regex pattern",
                )
            )

    return v


def _gen_value_fallback(col: ColumnSpec, rng: random.Random, row_index: int) -> object:
    # Null handling
    if col.nullable and rng.random() < 0.05:  # 5% nulls
        return None

    # Primary key: deterministic increasing integer (1..N)
    if col.primary_key:
        return row_index

    # Choices override
    if col.choices is not None:
        return rng.choice(col.choices)

    if col.dtype == "int":
        lo = int(col.min_value) if col.min_value is not None else 0
        hi = int(col.max_value) if col.max_value is not None else 1000
        return rng.randint(lo, hi)

    if col.dtype in {"float", "decimal"}:
        lo = float(col.min_value) if col.min_value is not None else 0.0
        hi = float(col.max_value) if col.max_value is not None else 1000.0
        return round(rng.uniform(lo, hi), 2)

    if col.dtype == "bool":
        return 1 if rng.random() < 0.5 else 0

    if col.dtype == "date":
        base = date(2020, 1, 1)
        d = base + timedelta(days=rng.randint(0, 3650))
        return _iso_date(d)

    if col.dtype == "datetime":
        base = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=rng.randint(0, 10_000_000))
        dt = base - timedelta(seconds=rng.randint(0, 3600 * 24 * 30))
        return _iso_datetime(dt)

    if col.dtype == "text":
        pattern = re.compile(col.pattern) if col.pattern else None
        letters = "abcdefghijklmnopqrstuvwxyz"

        def candidate() -> str:
            length = rng.randint(5, 14)
            return "".join(rng.choice(letters) for _ in range(length))

        for _ in range(50):
            s = candidate()
            if pattern is None or pattern.fullmatch(s):
                return s
        return candidate()

    if col.dtype == "bytes":
        params = col.params if isinstance(col.params, dict) else {}
        try:
            min_len = int(params.get("min_length", 8))
        except (TypeError, ValueError):
            min_len = 8
        try:
            max_len = int(params.get("max_length", min_len))
        except (TypeError, ValueError):
            max_len = min_len
        min_len = max(0, min_len)
        max_len = max(min_len, max_len)
        size = rng.randint(min_len, max_len)
        return bytes(rng.getrandbits(8) for _ in range(size))

    raise ValueError(
        _runtime_error(
            f"Column '{col.name}'",
            f"unsupported dtype '{col.dtype}' during runtime fallback generation",
            "use a supported dtype or configure a compatible generator",
        )
    )


def _order_columns_by_dependencies(cols: list[ColumnSpec]) -> list[ColumnSpec]:
    """
    Topological-ish ordering for column dependencies within a row.
    - columns without depends_on first
    - then columns whose deps are satisfied
    Raises on cycles / missing deps.
    """
    remaining = list(cols)
    ordered: list[ColumnSpec] = []
    produced: set[str] = set()

    # pre-seed: treat columns with no depends as ready
    while remaining:
        progressed = False
        for c in list(remaining):
            deps = getattr(c, "depends_on", None) or []
            if all(d in produced for d in deps):
                ordered.append(c)
                produced.add(c.name)
                remaining.remove(c)
                progressed = True
        if not progressed:
            # cycle or missing dependency
            stuck = [(c.name, getattr(c, "depends_on", None)) for c in remaining]
            raise ValueError(
                _runtime_error(
                    "Column dependency ordering",
                    f"cannot resolve dependencies {stuck}",
                    "remove circular depends_on references and reference only existing columns",
                )
            )
    return ordered


__all__ = ["_maybe_null", "_apply_numeric_post", "_gen_value", "_gen_value_fallback", "_order_columns_by_dependencies"]
