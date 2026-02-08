from __future__ import annotations
import random
import re
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
        REGISTRY[name] = fn
        return fn
    return deco

def get_generator(name: str) -> GeneratorFn:
    if name not in REGISTRY:
        raise KeyError(f"Unknown generator '{name}'. Registered: {sorted(REGISTRY.keys())}")
    return REGISTRY[name]


##----------------DATA TYPES----------------##
    ##---------------- LOCATIONS----------------##
@register("latitude")
def gen_latitude(params: Dict[str, Any], ctx: GenContext) -> float:
    # default: global land-ish range is complex; keep simple but realistic
    min_v = float(params.get("min", -90.0))
    max_v = float(params.get("max", 90.0))
    decimals = int(params.get("decimals", 6))
    return round(ctx.rng.uniform(min_v, max_v), decimals)

@register("longitude")
def gen_longitude(params: Dict[str, Any], ctx: GenContext) -> float:
    min_v = float(params.get("min", -180.0))
    max_v = float(params.get("max", 180.0))
    decimals = int(params.get("decimals", 6))
    return round(ctx.rng.uniform(min_v, max_v), decimals)


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
