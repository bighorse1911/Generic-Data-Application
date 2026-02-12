from __future__ import annotations
import random
import re
import math
from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from typing import Any, Callable, Dict, Optional

from src.project_paths import resolve_repo_path
from src.value_pools import load_csv_column

##----------------FUNCTIONAL----------------##
@dataclass
class GenContext:
    """
    Row-level context so generators can correlate.
    - row_index: 1..N
    - table: table name
    - row: mutable dict for already-generated values in this row
    - rng: stable per-table generator
    """
    row_index: int
    table: str
    row: Dict[str, Any]
    rng: random.Random

GeneratorFn = Callable[[Dict[str, Any], GenContext], Any]

REGISTRY: Dict[str, GeneratorFn] = {}

def register(name: str):
    def deco(fn: GeneratorFn) -> GeneratorFn:
        if name in REGISTRY:
            raise KeyError(
                f"Generator '{name}' is already registered. Existing: {sorted(REGISTRY.keys())}"
            )
        REGISTRY[name] = fn
        return fn
    return deco

def get_generator(name: str) -> GeneratorFn:
    if name not in REGISTRY:
        raise KeyError(f"Unknown generator '{name}'. Registered: {sorted(REGISTRY.keys())}")
    return REGISTRY[name]

def _generator_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _bounded_uniform_float(
    params: Dict[str, Any],
    ctx: GenContext,
    *,
    generator_name: str,
    default_min: float,
    default_max: float,
    default_decimals: int,
) -> float:
    min_v = float(params.get("min", default_min))
    max_v = float(params.get("max", default_max))
    decimals = int(params.get("decimals", default_decimals))
    if max_v < min_v:
        raise ValueError(
            f"{generator_name} generator: params.max ({max_v}) is less than params.min ({min_v}). "
            f"Fix: set params.max >= params.min."
        )
    if decimals < 0:
        raise ValueError(
            f"{generator_name} generator: params.decimals must be >= 0, got {decimals}. "
            "Fix: provide a non-negative integer for params.decimals."
        )
    return round(ctx.rng.uniform(min_v, max_v), decimals)


##----------------DATA TYPES----------------##
    ##---------------- LOCATIONS----------------##
@register("latitude")
def gen_latitude(params: Dict[str, Any], ctx: GenContext) -> float:
    # default: global land-ish range is complex; keep simple but realistic.
    return _bounded_uniform_float(
        params,
        ctx,
        generator_name="latitude",
        default_min=-90.0,
        default_max=90.0,
        default_decimals=6,
    )

@register("longitude")
def gen_longitude(params: Dict[str, Any], ctx: GenContext) -> float:
    return _bounded_uniform_float(
        params,
        ctx,
        generator_name="longitude",
        default_min=-180.0,
        default_max=180.0,
        default_decimals=6,
    )


@register("money")
def gen_money(params: Dict[str, Any], ctx: GenContext) -> float:
    return _bounded_uniform_float(
        params,
        ctx,
        generator_name="money",
        default_min=0.0,
        default_max=10000.0,
        default_decimals=2,
    )


@register("percent")
def gen_percent(params: Dict[str, Any], ctx: GenContext) -> float:
    return _bounded_uniform_float(
        params,
        ctx,
        generator_name="percent",
        default_min=0.0,
        default_max=100.0,
        default_decimals=2,
    )


    ##----------------DATETIME----------------##
@register("date")
def gen_date(params: Dict[str, Any], ctx: GenContext) -> str:
    """
    Returns ISO date 'YYYY-MM-DD'
    params:
      - start: '2020-01-01'
      - end: '2026-12-31'
    """
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
    """
    Returns ISO 8601 UTC timestamp: 'YYYY-MM-DDTHH:MM:SSZ'
    params:
      - start: '2020-01-01T00:00:00Z'
      - end:   '2026-12-31T23:59:59Z'
    """
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


    ##----------------CSV SAMPLING----------------##
@register("sample_csv")
def gen_sample_csv(params: Dict[str, Any], ctx: GenContext) -> str:
    path_value = params.get("path")
    if not isinstance(path_value, str) or path_value.strip() == "":
        raise ValueError(
            f"Table '{ctx.table}': generator 'sample_csv' requires params.path. "
            "Fix: set params.path to a CSV file path."
        )
    path = path_value.strip()
    resolved_path = resolve_repo_path(path)

    col_value = params.get("column_index", 0)
    try:
        col = int(col_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Table '{ctx.table}': generator 'sample_csv' params.column_index must be an integer. "
            "Fix: set params.column_index to 0 or greater."
        ) from exc
    if col < 0:
        raise ValueError(
            f"Table '{ctx.table}': generator 'sample_csv' params.column_index cannot be negative. "
            "Fix: set params.column_index to 0 or greater."
        )

    try:
        values = load_csv_column(str(resolved_path), col, skip_header=True)
    except FileNotFoundError as exc:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'sample_csv'",
                f"params.path '{path}' does not exist",
                "set params.path to an existing CSV file path",
            )
        ) from exc
    except ValueError as exc:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'sample_csv'",
                f"no non-empty values were loaded from column_index={col}",
                "choose a CSV column with non-empty values or change params.column_index",
            )
        ) from exc
    return ctx.rng.choice(values)


@register("if_then")
def gen_if_then(params: Dict[str, Any], ctx: GenContext) -> Any:
    if_col = params.get("if_column")
    if not isinstance(if_col, str) or if_col.strip() == "":
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                "params.if_column is required",
                "set params.if_column to a source column name and add it to depends_on",
            )
        )
    if_col = if_col.strip()

    if if_col not in ctx.row:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                f"if_column '{if_col}' is not available in row context",
                "set depends_on to include the source column so it generates first",
            )
        )

    op = params.get("operator", "==")
    if not isinstance(op, str) or op not in {"==", "!="}:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                f"unsupported operator '{op}'",
                "use operator '==' or '!='",
            )
        )

    if "value" not in params:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                "params.value is required",
                "set params.value to the comparison value",
            )
        )
    if "then_value" not in params or "else_value" not in params:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                "params.then_value and params.else_value are required",
                "set both output values for true/false branches",
            )
        )

    left = ctx.row[if_col]
    right = params["value"]
    condition = left == right if op == "==" else left != right
    return params["then_value"] if condition else params["else_value"]


##----------------COLUMN BEHAVIOUR----------------##

    ##----------------DISTRIBUTIONS----------------##
@register("normal")
def gen_normal(params, ctx: GenContext) -> float:
    mean = float(params.get("mean", 0.0))
    stdev = float(params.get("stdev", 1.0))
    decimals = int(params.get("decimals", 2))
    x = ctx.rng.gauss(mean, stdev)
    min_v = params.get("min", None)
    max_v = params.get("max", None)
    if min_v is not None:
        x = max(float(min_v), x)
    if max_v is not None:
        x = min(float(max_v), x)
    return round(x, decimals)

@register("uniform_int")
def gen_uniform_int(params, ctx):
    mn = int(params.get("min", 0))
    mx = int(params.get("max", 100))
    return ctx.rng.randint(mn, mx)

@register("uniform_float")
def gen_uniform_float(params, ctx):
    return _bounded_uniform_float(
        params,
        ctx,
        generator_name="uniform_float",
        default_min=0.0,
        default_max=1.0,
        default_decimals=3,
    )



@register("lognormal")
def gen_lognormal(params, ctx):
    # mu/sigma are log-space parameters; easier UX is median + sigma
    median = float(params.get("median", 50000))
    sigma = float(params.get("sigma", 0.5))
    mu = math.log(max(median, 1e-9))
    x = ctx.rng.lognormvariate(mu, sigma)
    decimals = int(params.get("decimals", 2))
    return round(x, decimals)

@register("choice_weighted")
def gen_choice_weighted(params, ctx):
    choices = params.get("choices", None)
    weights = params.get("weights", None)
    if not isinstance(choices, list) or not choices:
        raise ValueError(
            _generator_error(
                "Generator 'choice_weighted'",
                "params.choices must be a non-empty list",
                "set params.choices to one or more values",
            )
        )
    if weights is None:
        # equal weights
        return ctx.rng.choice(choices)
    if not isinstance(weights, list) or len(weights) != len(choices):
        raise ValueError(
            _generator_error(
                "Generator 'choice_weighted'",
                "params.weights must match params.choices length",
                "provide one numeric weight per choice or omit params.weights",
            )
        )
    return ctx.rng.choices(choices, weights=weights, k=1)[0]


    ##----------------CORRELATIONS----------------##
@register("salary_from_age")
def gen_salary_from_age(params, ctx: GenContext) -> int:
    age_col = params.get("age_col", "age")
    age = int(ctx.row.get(age_col, 30))

    # Simple realistic-ish curve:
    # early career -> mid -> plateau
    base = 35000 + (age - 18) * 2500
    base = min(base, 140000)

    # add noise
    noise = int(ctx.rng.gauss(0, 8000))
    val = max(20000, base + noise)

    # optional clamp
    min_v = int(params.get("min", 20000))
    max_v = int(params.get("max", 250000))
    return max(min_v, min(max_v, val))
