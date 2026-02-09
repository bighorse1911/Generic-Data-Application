from __future__ import annotations
import random
import re
import math
from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from typing import Any, Callable, Dict, Optional

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
        raise ValueError("date generator: end < start")
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
        raise ValueError("timestamp_utc generator: end < start")

    span = int((end - start).total_seconds())
    dt = start + timedelta(seconds=ctx.rng.randint(0, span))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


    ##----------------CSV SAMPLING----------------##
@register("sample_csv")
def gen_sample_csv(params: Dict[str, Any], ctx: GenContext) -> str:
    path = str(params["path"])
    col = int(params.get("column_index", 0))
    values = load_csv_column(path, col, skip_header=True)
    return ctx.rng.choice(values)


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
        raise ValueError("choice_weighted requires params.choices = [...]")
    if weights is None:
        # equal weights
        return ctx.rng.choice(choices)
    if not isinstance(weights, list) or len(weights) != len(choices):
        raise ValueError("choice_weighted requires params.weights same length as choices")
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
