"""Compatibility facade for generator registry and built-in generators."""

from __future__ import annotations

from src.generation.generator_common import (
    _generator_error,
    _is_scalar_json_value,
    _parse_offset_bounds,
    _parse_positive_weight_list,
)
from src.generation.generator_state import (
    _DERIVED_EXPRESSION_STATE,
    _ORDERED_CHOICE_STATE,
    _STATE_TRANSITION_CONFIG_STATE,
    _STATE_TRANSITION_ENTITY_STATE,
    reset_runtime_generator_state,
)
from src.generation.registry_core import GenContext, GeneratorFn, REGISTRY, get_generator, register

_BUILTINS_BOOTSTRAPPED = False


def _bootstrap_builtin_generators() -> None:
    global _BUILTINS_BOOTSTRAPPED
    if _BUILTINS_BOOTSTRAPPED:
        return

    from src.generation.builtins import categorical as _categorical  # noqa: F401
    from src.generation.builtins import conditional as _conditional  # noqa: F401
    from src.generation.builtins import derived_expr as _derived_expr  # noqa: F401
    from src.generation.builtins import lifecycle as _lifecycle  # noqa: F401
    from src.generation.builtins import numeric as _numeric  # noqa: F401
    from src.generation.builtins import temporal as _temporal  # noqa: F401

    _BUILTINS_BOOTSTRAPPED = True


_bootstrap_builtin_generators()

from src.generation.builtins.categorical import (  # noqa: E402
    gen_choice_weighted,
    gen_hierarchical_category,
    gen_ordered_choice,
    gen_sample_csv,
)
from src.generation.builtins.conditional import gen_if_then  # noqa: E402
from src.generation.builtins.derived_expr import gen_derived_expr  # noqa: E402
from src.generation.builtins.lifecycle import gen_state_transition  # noqa: E402
from src.generation.builtins.numeric import (  # noqa: E402
    gen_latitude,
    gen_lognormal,
    gen_longitude,
    gen_money,
    gen_normal,
    gen_percent,
    gen_salary_from_age,
    gen_uniform_float,
    gen_uniform_int,
)
from src.generation.builtins.temporal import gen_date, gen_time_offset, gen_timestamp_utc  # noqa: E402

__all__ = [
    "GeneratorFn",
    "GenContext",
    "REGISTRY",
    "register",
    "get_generator",
    "reset_runtime_generator_state",
    "gen_latitude",
    "gen_longitude",
    "gen_money",
    "gen_percent",
    "gen_date",
    "gen_timestamp_utc",
    "gen_sample_csv",
    "gen_if_then",
    "gen_hierarchical_category",
    "gen_time_offset",
    "gen_normal",
    "gen_uniform_int",
    "gen_uniform_float",
    "gen_lognormal",
    "gen_choice_weighted",
    "gen_ordered_choice",
    "gen_state_transition",
    "gen_derived_expr",
    "gen_salary_from_age",
]
