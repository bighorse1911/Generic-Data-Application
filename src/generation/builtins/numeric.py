from __future__ import annotations

import math
from typing import Any, Dict

from src.generation.generator_common import _generator_error
from src.generation.registry_core import GenContext, register


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


@register("latitude")
def gen_latitude(params: Dict[str, Any], ctx: GenContext) -> float:
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


@register("normal")
def gen_normal(params, ctx: GenContext) -> float:
    location = f"Table '{ctx.table}', generator 'normal'"

    try:
        mean = float(params.get("mean", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.mean must be numeric",
                "set params.mean to a number",
            )
        ) from exc

    has_stdev = "stdev" in params
    has_stddev = "stddev" in params
    if has_stdev and has_stddev:
        raise ValueError(
            _generator_error(
                location,
                "params.stdev and params.stddev cannot both be set",
                "provide only one standard deviation key",
            )
        )
    stdev_key = "stddev" if has_stddev else "stdev"
    try:
        stdev = float(params.get(stdev_key, 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                f"params.{stdev_key} must be numeric",
                f"set params.{stdev_key} to a positive number",
            )
        ) from exc
    if stdev <= 0:
        raise ValueError(
            _generator_error(
                location,
                f"params.{stdev_key} must be > 0",
                f"set params.{stdev_key} to a positive number",
            )
        )

    try:
        decimals = int(params.get("decimals", 2))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.decimals must be an integer",
                "set params.decimals to 0 or greater",
            )
        ) from exc
    if decimals < 0:
        raise ValueError(
            _generator_error(
                location,
                "params.decimals must be >= 0",
                "set params.decimals to 0 or greater",
            )
        )

    x = ctx.rng.gauss(mean, stdev)
    min_v = params.get("min")
    max_v = params.get("max")
    min_num = None
    max_num = None
    if min_v is not None:
        try:
            min_num = float(min_v)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _generator_error(
                    location,
                    "params.min must be numeric",
                    "set params.min to a numeric lower bound or omit it",
                )
            ) from exc
    if max_v is not None:
        try:
            max_num = float(max_v)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _generator_error(
                    location,
                    "params.max must be numeric",
                    "set params.max to a numeric upper bound or omit it",
                )
            ) from exc
    if min_num is not None and max_num is not None and max_num < min_num:
        raise ValueError(
            _generator_error(
                location,
                "params.max is less than params.min",
                "set params.max >= params.min",
            )
        )
    if min_num is not None:
        x = max(min_num, x)
    if max_num is not None:
        x = min(max_num, x)
    return round(x, decimals)


@register("uniform_int")
def gen_uniform_int(params, ctx):
    location = f"Table '{ctx.table}', generator 'uniform_int'"
    try:
        mn = int(params.get("min", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.min must be an integer",
                "set params.min to a whole-number lower bound",
            )
        ) from exc
    try:
        mx = int(params.get("max", 100))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.max must be an integer",
                "set params.max to a whole-number upper bound",
            )
        ) from exc
    if mx < mn:
        raise ValueError(
            _generator_error(
                location,
                "params.max is less than params.min",
                "set params.max >= params.min",
            )
        )
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
    location = f"Table '{ctx.table}', generator 'lognormal'"
    try:
        median = float(params.get("median", 50000))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.median must be numeric",
                "set params.median to a positive number",
            )
        ) from exc
    try:
        sigma = float(params.get("sigma", 0.5))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.sigma must be numeric",
                "set params.sigma to a positive number",
            )
        ) from exc
    if median <= 0:
        raise ValueError(
            _generator_error(
                location,
                "params.median must be > 0",
                "set params.median to a positive number",
            )
        )
    if sigma <= 0:
        raise ValueError(
            _generator_error(
                location,
                "params.sigma must be > 0",
                "set params.sigma to a positive number",
            )
        )

    mu = math.log(max(median, 1e-9))
    x = ctx.rng.lognormvariate(mu, sigma)
    try:
        decimals = int(params.get("decimals", 2))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.decimals must be an integer",
                "set params.decimals to 0 or greater",
            )
        ) from exc
    if decimals < 0:
        raise ValueError(
            _generator_error(
                location,
                "params.decimals must be >= 0",
                "set params.decimals to 0 or greater",
            )
        )

    min_v = params.get("min")
    max_v = params.get("max")
    min_num = None
    max_num = None
    if min_v is not None:
        try:
            min_num = float(min_v)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _generator_error(
                    location,
                    "params.min must be numeric",
                    "set params.min to a numeric lower bound or omit it",
                )
            ) from exc
    if max_v is not None:
        try:
            max_num = float(max_v)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _generator_error(
                    location,
                    "params.max must be numeric",
                    "set params.max to a numeric upper bound or omit it",
                )
            ) from exc
    if min_num is not None and max_num is not None and max_num < min_num:
        raise ValueError(
            _generator_error(
                location,
                "params.max is less than params.min",
                "set params.max >= params.min",
            )
        )
    if min_num is not None:
        x = max(min_num, x)
    if max_num is not None:
        x = min(max_num, x)
    return round(x, decimals)


@register("salary_from_age")
def gen_salary_from_age(params, ctx: GenContext) -> int:
    age_col = params.get("age_col", "age")
    age = int(ctx.row.get(age_col, 30))

    base = 35000 + (age - 18) * 2500
    base = min(base, 140000)

    noise = int(ctx.rng.gauss(0, 8000))
    val = max(20000, base + noise)

    min_v = int(params.get("min", 20000))
    max_v = int(params.get("max", 250000))
    return max(min_v, min(max_v, val))


__all__ = [
    "gen_latitude",
    "gen_lognormal",
    "gen_longitude",
    "gen_money",
    "gen_normal",
    "gen_percent",
    "gen_salary_from_age",
    "gen_uniform_float",
    "gen_uniform_int",
]
