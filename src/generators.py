from __future__ import annotations
import random
import re
import math
from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from typing import Any, Callable, Dict, Optional

from src.derived_expression import CompiledDerivedExpression
from src.derived_expression import compile_derived_expression
from src.derived_expression import evaluate_derived_expression
from src.derived_expression import is_iso_date_text
from src.derived_expression import is_iso_datetime_text
from src.project_paths import resolve_repo_path
from src.value_pools import load_csv_column, load_csv_column_by_match

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
    column: str = ""
    dtype: str = ""

GeneratorFn = Callable[[Dict[str, Any], GenContext], Any]

REGISTRY: Dict[str, GeneratorFn] = {}
_ORDERED_CHOICE_STATE: Dict[tuple[str, str], Dict[str, Any]] = {}
_STATE_TRANSITION_CONFIG_STATE: Dict[tuple[str, str], Dict[str, Any]] = {}
_STATE_TRANSITION_ENTITY_STATE: Dict[tuple[str, str, tuple[str, str]], Dict[str, Any]] = {}
_DERIVED_EXPRESSION_STATE: Dict[tuple[str, str], CompiledDerivedExpression] = {}

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


def reset_runtime_generator_state() -> None:
    _ORDERED_CHOICE_STATE.clear()
    _STATE_TRANSITION_CONFIG_STATE.clear()
    _STATE_TRANSITION_ENTITY_STATE.clear()
    _DERIVED_EXPRESSION_STATE.clear()

def _generator_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _parse_offset_bounds(
    params: Dict[str, Any],
    *,
    min_key: str,
    max_key: str,
    location: str,
    unit_label: str,
) -> tuple[int, int]:
    min_raw = params.get(min_key, 0)
    max_raw = params.get(max_key, min_raw)
    try:
        min_v = int(min_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                f"params.{min_key} must be an integer",
                f"set params.{min_key} to a whole-number {unit_label} offset",
            )
        ) from exc
    try:
        max_v = int(max_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                f"params.{max_key} must be an integer",
                f"set params.{max_key} to a whole-number {unit_label} offset",
            )
        ) from exc
    if min_v < 0 or max_v < 0:
        raise ValueError(
            _generator_error(
                location,
                f"params.{min_key} and params.{max_key} must be >= 0",
                f"use non-negative {unit_label} offsets",
            )
        )
    if max_v < min_v:
        raise ValueError(
            _generator_error(
                location,
                f"params.{max_key} is less than params.{min_key}",
                f"set params.{max_key} >= params.{min_key}",
            )
        )
    return min_v, max_v


def _is_scalar_json_value(value: Any) -> bool:
    return not isinstance(value, (dict, list))


def _parse_positive_weight_list(
    raw_weights: Any,
    *,
    location: str,
    field_name: str,
) -> list[float]:
    if not isinstance(raw_weights, list) or len(raw_weights) == 0:
        raise ValueError(
            _generator_error(
                location,
                f"params.{field_name} must be a non-empty list",
                f"set params.{field_name} to one or more numeric weights",
            )
        )
    parsed: list[float] = []
    for idx, raw in enumerate(raw_weights):
        try:
            weight = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.{field_name}[{idx}] must be numeric",
                    f"use numeric weights in params.{field_name}",
                )
            ) from exc
        if weight < 0:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.{field_name}[{idx}] cannot be negative",
                    f"use non-negative weights in params.{field_name}",
                )
            )
        parsed.append(weight)
    if not any(weight > 0 for weight in parsed):
        raise ValueError(
            _generator_error(
                location,
                f"params.{field_name} must include at least one value > 0",
                f"set one or more params.{field_name} entries above zero",
            )
        )
    return parsed


def _is_valid_state_transition_scalar(value: Any) -> bool:
    return _is_scalar_json_value(value) and not isinstance(value, bool)


def _normalize_state_transition_states(params: Dict[str, Any], *, location: str) -> tuple[list[Any], str]:
    raw_states = params.get("states")
    if not isinstance(raw_states, list) or len(raw_states) == 0:
        raise ValueError(
            _generator_error(
                location,
                "params.states must be a non-empty list",
                "set params.states to one or more text/int state values",
            )
        )

    states: list[Any] = []
    seen: set[tuple[str, str]] = set()
    state_kind: str | None = None
    for idx, raw_state in enumerate(raw_states):
        if not _is_valid_state_transition_scalar(raw_state):
            raise ValueError(
                _generator_error(
                    location,
                    f"params.states[{idx}] must be a scalar text/int value",
                    "use string or integer state values only",
                )
            )

        if isinstance(raw_state, int):
            kind = "int"
            normalized: Any = raw_state
        elif isinstance(raw_state, str):
            if raw_state.strip() == "":
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.states[{idx}] cannot be empty",
                        "use non-empty state strings",
                    )
                )
            kind = "text"
            normalized = raw_state
        else:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.states[{idx}] has unsupported type '{type(raw_state).__name__}'",
                    "use only string or integer states",
                )
            )

        if state_kind is None:
            state_kind = kind
        elif state_kind != kind:
            raise ValueError(
                _generator_error(
                    location,
                    "params.states cannot mix text and int values",
                    "use all-text or all-int states",
                )
            )

        identity = (type(normalized).__name__, repr(normalized))
        if identity in seen:
            raise ValueError(
                _generator_error(
                    location,
                    "params.states contains duplicate values",
                    "list each state only once",
                )
            )
        seen.add(identity)
        states.append(normalized)

    assert state_kind is not None
    return states, state_kind


def _coerce_state_transition_value(
    raw_value: Any,
    *,
    states: list[Any],
    state_kind: str,
    location: str,
    field_name: str,
    allow_int_string: bool,
) -> Any:
    allowed_lookup = set(states)
    if state_kind == "int":
        if isinstance(raw_value, bool):
            raise ValueError(
                _generator_error(
                    location,
                    f"{field_name} has unsupported boolean value",
                    "use integer state values",
                )
            )
        candidate: int
        if isinstance(raw_value, int):
            candidate = raw_value
        elif allow_int_string and isinstance(raw_value, str) and raw_value.strip() != "":
            try:
                candidate = int(raw_value.strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _generator_error(
                        location,
                        f"{field_name} value '{raw_value}' is not a valid integer state",
                        "use integer states (or integer-like keys for JSON objects)",
                    )
                ) from exc
        else:
            raise ValueError(
                _generator_error(
                    location,
                    f"{field_name} must use integer states",
                    "use integer states that exist in params.states",
                )
            )
        if candidate not in allowed_lookup:
            raise ValueError(
                _generator_error(
                    location,
                    f"{field_name} value '{candidate}' is not in params.states",
                    "use only state values declared in params.states",
                )
            )
        return candidate

    if not isinstance(raw_value, str):
        raise ValueError(
            _generator_error(
                location,
                f"{field_name} must use text states",
                "use string states that exist in params.states",
            )
        )
    if raw_value not in allowed_lookup:
        raise ValueError(
            _generator_error(
                location,
                f"{field_name} value '{raw_value}' is not in params.states",
                "use only state values declared in params.states",
            )
        )
    return raw_value


def _build_state_transition_config(params: Dict[str, Any], *, location: str) -> Dict[str, Any]:
    states, state_kind = _normalize_state_transition_states(params, location=location)
    states_list = list(states)

    start_state_raw = params.get("start_state")
    start_weights_raw = params.get("start_weights")
    if start_state_raw is not None and start_weights_raw is not None:
        raise ValueError(
            _generator_error(
                location,
                "params.start_state and params.start_weights cannot both be set",
                "set either a fixed start_state or weighted start_weights",
            )
        )

    start_state = states_list[0]
    start_weights: list[float] | None = None
    if start_state_raw is not None:
        start_state = _coerce_state_transition_value(
            start_state_raw,
            states=states_list,
            state_kind=state_kind,
            location=location,
            field_name="params.start_state",
            allow_int_string=False,
        )
    elif start_weights_raw is not None:
        if not isinstance(start_weights_raw, dict):
            raise ValueError(
                _generator_error(
                    location,
                    "params.start_weights must be an object when provided",
                    "set params.start_weights to an object mapping states to weights",
                )
            )
        normalized_start_weights: dict[Any, Any] = {}
        for raw_key, raw_weight in start_weights_raw.items():
            state_value = _coerce_state_transition_value(
                raw_key,
                states=states_list,
                state_kind=state_kind,
                location=location,
                field_name="params.start_weights key",
                allow_int_string=True,
            )
            if state_value in normalized_start_weights:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.start_weights has duplicate key '{raw_key}' after normalization",
                        "use one unique start weight per state",
                    )
                )
            normalized_start_weights[state_value] = raw_weight
        if set(normalized_start_weights.keys()) != set(states_list):
            raise ValueError(
                _generator_error(
                    location,
                    "params.start_weights keys must exactly match params.states",
                    "provide one start weight for each state",
                )
            )

        parsed_weights: list[float] = []
        for state_value in states_list:
            raw_weight = normalized_start_weights.get(state_value)
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.start_weights['{state_value}'] must be numeric",
                        "use numeric non-negative start weights",
                    )
                ) from exc
            if weight < 0:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.start_weights['{state_value}'] cannot be negative",
                        "use non-negative start weights",
                    )
                )
            parsed_weights.append(weight)
        if not any(weight > 0 for weight in parsed_weights):
            raise ValueError(
                _generator_error(
                    location,
                    "params.start_weights must include at least one value > 0",
                    "set one or more start weights above zero",
                )
            )
        start_weights = parsed_weights

    terminal_states_raw = params.get("terminal_states", [])
    if not isinstance(terminal_states_raw, list):
        raise ValueError(
            _generator_error(
                location,
                "params.terminal_states must be a list when provided",
                "set params.terminal_states to a list of state values or omit it",
            )
        )
    terminal_states: set[Any] = set()
    for idx, raw_terminal in enumerate(terminal_states_raw):
        terminal_state = _coerce_state_transition_value(
            raw_terminal,
            states=states_list,
            state_kind=state_kind,
            location=location,
            field_name=f"params.terminal_states[{idx}]",
            allow_int_string=False,
        )
        if terminal_state in terminal_states:
            raise ValueError(
                _generator_error(
                    location,
                    "params.terminal_states contains duplicate values",
                    "list each terminal state only once",
                )
            )
        terminal_states.add(terminal_state)

    dwell_min_raw = params.get("dwell_min", 1)
    dwell_max_raw = params.get("dwell_max", dwell_min_raw)
    try:
        dwell_min = int(dwell_min_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.dwell_min must be an integer",
                "set params.dwell_min to 1 or greater",
            )
        ) from exc
    try:
        dwell_max = int(dwell_max_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.dwell_max must be an integer",
                "set params.dwell_max to an integer >= params.dwell_min",
            )
        ) from exc
    if dwell_min < 1:
        raise ValueError(
            _generator_error(
                location,
                "params.dwell_min must be >= 1",
                "set params.dwell_min to 1 or greater",
            )
        )
    if dwell_max < dwell_min:
        raise ValueError(
            _generator_error(
                location,
                "params.dwell_max cannot be less than params.dwell_min",
                "set params.dwell_max >= params.dwell_min",
            )
        )

    dwell_by_state_raw = params.get("dwell_by_state")
    dwell_by_state: dict[Any, tuple[int, int]] = {}
    if dwell_by_state_raw is not None:
        if not isinstance(dwell_by_state_raw, dict):
            raise ValueError(
                _generator_error(
                    location,
                    "params.dwell_by_state must be an object when provided",
                    "set params.dwell_by_state to a state->min/max object map",
                )
            )
        for raw_key, raw_bounds in dwell_by_state_raw.items():
            state_value = _coerce_state_transition_value(
                raw_key,
                states=states_list,
                state_kind=state_kind,
                location=location,
                field_name="params.dwell_by_state key",
                allow_int_string=True,
            )
            if state_value in dwell_by_state:
                raise ValueError(
                    _generator_error(
                        location,
                        "params.dwell_by_state has duplicate keys after normalization",
                        "use one dwell override per state",
                    )
                )
            if not isinstance(raw_bounds, dict):
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.dwell_by_state['{raw_key}'] must be an object",
                        "set min/max integer bounds for each state entry",
                    )
                )
            min_raw = raw_bounds.get("min", dwell_min)
            max_raw = raw_bounds.get("max", min_raw)
            try:
                min_bound = int(min_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.dwell_by_state['{raw_key}'].min must be an integer",
                        "set a whole-number min dwell >= 1",
                    )
                ) from exc
            try:
                max_bound = int(max_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.dwell_by_state['{raw_key}'].max must be an integer",
                        "set a whole-number max dwell >= min",
                    )
                ) from exc
            if min_bound < 1:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.dwell_by_state['{raw_key}'].min must be >= 1",
                        "set per-state min dwell to 1 or greater",
                    )
                )
            if max_bound < min_bound:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.dwell_by_state['{raw_key}'].max cannot be less than min",
                        "set per-state max dwell >= min",
                    )
                )
            dwell_by_state[state_value] = (min_bound, max_bound)

    transitions_raw = params.get("transitions")
    if not isinstance(transitions_raw, dict) or len(transitions_raw) == 0:
        raise ValueError(
            _generator_error(
                location,
                "params.transitions must be a non-empty object",
                "set params.transitions like {'new': {'active': 1.0}}",
            )
        )
    transitions: dict[Any, tuple[list[Any], list[float]]] = {}
    for raw_from, raw_targets in transitions_raw.items():
        from_state = _coerce_state_transition_value(
            raw_from,
            states=states_list,
            state_kind=state_kind,
            location=location,
            field_name="params.transitions key",
            allow_int_string=True,
        )
        if from_state in transitions:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.transitions has duplicate from-state '{raw_from}' after normalization",
                    "use one unique from-state entry per declared state",
                )
            )
        if not isinstance(raw_targets, dict) or len(raw_targets) == 0:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.transitions['{raw_from}'] must be a non-empty object",
                    "set one or more outbound state weights",
                )
            )
        targets: list[Any] = []
        weights: list[float] = []
        for raw_to, raw_weight in raw_targets.items():
            to_state = _coerce_state_transition_value(
                raw_to,
                states=states_list,
                state_kind=state_kind,
                location=location,
                field_name=f"params.transitions['{raw_from}'] key",
                allow_int_string=True,
            )
            if to_state == from_state:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.transitions['{raw_from}'] cannot include self-transition '{raw_to}'",
                        "remove self-transition edges and model state hold time with dwell controls",
                    )
                )
            if to_state in targets:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.transitions['{raw_from}'] contains duplicate to-state '{raw_to}' after normalization",
                        "use one unique target entry per outbound transition",
                    )
                )
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.transitions['{raw_from}']['{raw_to}'] must be numeric",
                        "use numeric non-negative transition weights",
                    )
                ) from exc
            if weight < 0:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.transitions['{raw_from}']['{raw_to}'] cannot be negative",
                        "use non-negative transition weights",
                    )
                )
            targets.append(to_state)
            weights.append(weight)
        if not any(weight > 0 for weight in weights):
            raise ValueError(
                _generator_error(
                    location,
                    f"params.transitions['{raw_from}'] must include at least one weight > 0",
                    "set one or more outbound weights above zero",
                )
            )
        transitions[from_state] = (targets, weights)

    for state_value in states_list:
        if state_value in terminal_states:
            outbound = transitions.get(state_value)
            if outbound is not None and len(outbound[0]) > 0:
                raise ValueError(
                    _generator_error(
                        location,
                        f"terminal state '{state_value}' cannot define outbound transitions",
                        "remove transition entries for terminal states",
                    )
                )
            continue
        if state_value not in transitions:
            raise ValueError(
                _generator_error(
                    location,
                    f"non-terminal state '{state_value}' is missing transition weights",
                    "add one or more outbound transition targets for each non-terminal state",
                )
            )

    return {
        "states": states_list,
        "start_state": start_state,
        "start_weights": start_weights,
        "transitions": transitions,
        "terminal_states": terminal_states,
        "dwell_global": (dwell_min, dwell_max),
        "dwell_by_state": dwell_by_state,
    }


def _state_transition_dwell_bounds(config: Dict[str, Any], state_value: Any) -> tuple[int, int]:
    dwell_by_state = config["dwell_by_state"]
    if state_value in dwell_by_state:
        return dwell_by_state[state_value]
    return config["dwell_global"]


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
    location = f"Table '{ctx.table}', generator 'sample_csv'"
    path_value = params.get("path")
    if not isinstance(path_value, str) or path_value.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                "requires params.path",
                "set params.path to a CSV file path",
            )
        )
    path = path_value.strip()
    resolved_path = resolve_repo_path(path)

    col_value = params.get("column_index", 0)
    try:
        col = int(col_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.column_index must be an integer",
                "set params.column_index to 0 or greater",
            )
        ) from exc
    if col < 0:
        raise ValueError(
            _generator_error(
                location,
                "params.column_index cannot be negative",
                "set params.column_index to 0 or greater",
            )
        )

    match_column_raw = params.get("match_column")
    if match_column_raw is not None and not isinstance(match_column_raw, str):
        raise ValueError(
            _generator_error(
                location,
                "params.match_column must be a string when provided",
                "set params.match_column to a source column name or remove it",
            )
        )
    match_column = None
    if isinstance(match_column_raw, str):
        stripped = match_column_raw.strip()
        if stripped != "":
            match_column = stripped

    match_column_index_raw = params.get("match_column_index")
    if match_column is None and match_column_index_raw is not None:
        raise ValueError(
            _generator_error(
                location,
                "params.match_column_index requires params.match_column",
                "set params.match_column to a source column name or remove params.match_column_index",
            )
        )

    if match_column is None:
        try:
            values = load_csv_column(str(resolved_path), col, skip_header=True)
        except FileNotFoundError as exc:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.path '{path}' does not exist",
                    "set params.path to an existing CSV file path",
                )
            ) from exc
        except ValueError as exc:
            raise ValueError(
                _generator_error(
                    location,
                    f"no non-empty values were loaded from column_index={col}",
                    "choose a CSV column with non-empty values or change params.column_index",
                )
            ) from exc
        return ctx.rng.choice(values)

    if match_column not in ctx.row:
        raise ValueError(
            _generator_error(
                location,
                f"match_column '{match_column}' is not available in row context",
                "add the source column to depends_on so it generates first",
            )
        )

    if match_column_index_raw is None:
        raise ValueError(
            _generator_error(
                location,
                "params.match_column_index is required when params.match_column is set",
                "set params.match_column_index to the CSV column index that should match params.match_column",
            )
        )

    try:
        match_column_index = int(match_column_index_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.match_column_index must be an integer",
                "set params.match_column_index to 0 or greater",
            )
        ) from exc
    if match_column_index < 0:
        raise ValueError(
            _generator_error(
                location,
                "params.match_column_index cannot be negative",
                "set params.match_column_index to 0 or greater",
            )
        )

    try:
        values_by_match = load_csv_column_by_match(
            str(resolved_path),
            col,
            match_column_index,
            skip_header=True,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            _generator_error(
                location,
                f"params.path '{path}' does not exist",
                "set params.path to an existing CSV file path",
            )
        ) from exc
    except ValueError as exc:
        raise ValueError(
            _generator_error(
                location,
                f"no non-empty values were loaded from column_index={col} using match_column_index={match_column_index}",
                "choose CSV columns with non-empty values or adjust column indexes",
            )
        ) from exc

    match_value = str(ctx.row.get(match_column, "")).strip()
    candidates = values_by_match.get(match_value)
    if not candidates:
        raise ValueError(
            _generator_error(
                location,
                f"no CSV rows matched match_column '{match_column}' value '{match_value}' using match_column_index={match_column_index}",
                "ensure source values exist in the CSV match column or adjust params.match_column_index",
            )
        )
    return ctx.rng.choice(candidates)


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


@register("hierarchical_category")
def gen_hierarchical_category(params: Dict[str, Any], ctx: GenContext) -> Any:
    location = f"Table '{ctx.table}', generator 'hierarchical_category'"
    parent_col = params.get("parent_column")
    if not isinstance(parent_col, str) or parent_col.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                "params.parent_column is required",
                "set params.parent_column to a source category column name and add it to depends_on",
            )
        )
    parent_col = parent_col.strip()
    if parent_col not in ctx.row:
        raise ValueError(
            _generator_error(
                location,
                f"parent_column '{parent_col}' is not available in row context",
                "set depends_on to include the source column so it generates first",
            )
        )

    hierarchy = params.get("hierarchy")
    if not isinstance(hierarchy, dict) or not hierarchy:
        raise ValueError(
            _generator_error(
                location,
                "params.hierarchy must be a non-empty object",
                "set params.hierarchy to a mapping like {\"Parent\": [\"ChildA\", \"ChildB\"]}",
            )
        )

    parent_value = ctx.row[parent_col]
    candidates = hierarchy.get(parent_value)
    if candidates is None:
        candidates = hierarchy.get(str(parent_value))
    if candidates is None:
        candidates = params.get("default_children")
    if not isinstance(candidates, list) or len(candidates) == 0:
        raise ValueError(
            _generator_error(
                location,
                f"no child categories configured for parent value '{parent_value}'",
                "add that parent value to params.hierarchy or set params.default_children",
            )
        )
    if any(not _is_scalar_json_value(item) for item in candidates):
        raise ValueError(
            _generator_error(
                location,
                "child category values must be scalar JSON values",
                "use string/number/bool/null values in hierarchy lists",
            )
        )
    return ctx.rng.choice(candidates)


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


##----------------COLUMN BEHAVIOUR----------------##

    ##----------------DISTRIBUTIONS----------------##
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
    # mu/sigma are log-space parameters; easier UX is median + sigma
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
    numeric_weights: list[float] = []
    for idx, weight in enumerate(weights):
        try:
            weight_num = float(weight)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _generator_error(
                    "Generator 'choice_weighted'",
                    f"params.weights[{idx}] must be numeric",
                    "provide numeric weights (for example 0.2, 1, 3.5)",
                )
            ) from exc
        if weight_num < 0:
            raise ValueError(
                _generator_error(
                    "Generator 'choice_weighted'",
                    f"params.weights[{idx}] cannot be negative",
                    "use weights >= 0 and keep at least one weight > 0",
                )
            )
        numeric_weights.append(weight_num)

    if not any(w > 0 for w in numeric_weights):
        raise ValueError(
            _generator_error(
                "Generator 'choice_weighted'",
                "params.weights must include at least one value > 0",
                "set one or more weights above zero",
            )
        )
    return ctx.rng.choices(choices, weights=numeric_weights, k=1)[0]


@register("ordered_choice")
def gen_ordered_choice(params: Dict[str, Any], ctx: GenContext) -> Any:
    location = f"Table '{ctx.table}', generator 'ordered_choice'"
    orders_raw = params.get("orders")
    if not isinstance(orders_raw, dict) or not orders_raw:
        raise ValueError(
            _generator_error(
                location,
                "params.orders must be a non-empty object",
                "set params.orders to a mapping like {'A': ['one', 'two'], 'B': ['three', 'four']}",
            )
        )

    orders: dict[str, list[Any]] = {}
    for order_name_raw, sequence_raw in orders_raw.items():
        if not isinstance(order_name_raw, str) or order_name_raw.strip() == "":
            raise ValueError(
                _generator_error(
                    location,
                    "params.orders keys must be non-empty strings",
                    "use order names like 'A' or 'OrderB' as object keys",
                )
            )
        order_name = order_name_raw.strip()
        if order_name in orders:
            raise ValueError(
                _generator_error(
                    location,
                    f"duplicate order key '{order_name}' after normalization",
                    "use unique order names in params.orders",
                )
            )
        if not isinstance(sequence_raw, list) or len(sequence_raw) == 0:
            raise ValueError(
                _generator_error(
                    location,
                    f"params.orders['{order_name}'] must be a non-empty list",
                    "provide one or more ordered choice values per order",
                )
            )
        if any(not _is_scalar_json_value(value) for value in sequence_raw):
            raise ValueError(
                _generator_error(
                    location,
                    f"params.orders['{order_name}'] values must be scalar JSON values",
                    "use string/number/bool/null entries in order lists",
                )
            )
        orders[order_name] = sequence_raw

    order_names = list(orders.keys())
    order_weights_raw = params.get("order_weights")
    if order_weights_raw is None:
        order_weights = [1.0] * len(order_names)
    else:
        if not isinstance(order_weights_raw, dict):
            raise ValueError(
                _generator_error(
                    location,
                    "params.order_weights must be an object when provided",
                    "set params.order_weights to a mapping like {'A': 0.7, 'B': 0.3}",
                )
            )
        missing_orders = [name for name in order_names if name not in order_weights_raw]
        extra_orders = [name for name in order_weights_raw.keys() if name not in orders]
        if missing_orders or extra_orders:
            missing_text = ", ".join(missing_orders) if missing_orders else "(none)"
            extra_text = ", ".join(str(name) for name in extra_orders) if extra_orders else "(none)"
            raise ValueError(
                _generator_error(
                    location,
                    f"params.order_weights keys must exactly match params.orders keys (missing: {missing_text}; extra: {extra_text})",
                    "add one weight per order and remove unknown order_weights keys",
                )
            )
        order_weights = []
        for order_name in order_names:
            raw_weight = order_weights_raw.get(order_name)
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.order_weights['{order_name}'] must be numeric",
                        "use numeric order weights (for example 0.2, 1, 3.5)",
                    )
                ) from exc
            if weight < 0:
                raise ValueError(
                    _generator_error(
                        location,
                        f"params.order_weights['{order_name}'] cannot be negative",
                        "use non-negative order weights and keep at least one above zero",
                    )
                )
            order_weights.append(weight)
        if not any(weight > 0 for weight in order_weights):
            raise ValueError(
                _generator_error(
                    location,
                    "params.order_weights must include at least one value > 0",
                    "set one or more order weights above zero",
                )
            )

    move_weights = _parse_positive_weight_list(
        params.get("move_weights", [0.0, 1.0]),
        location=location,
        field_name="move_weights",
    )

    start_index_raw = params.get("start_index", 0)
    try:
        start_index = int(start_index_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _generator_error(
                location,
                "params.start_index must be an integer",
                "set params.start_index to 0 or greater",
            )
        ) from exc
    if start_index < 0:
        raise ValueError(
            _generator_error(
                location,
                "params.start_index cannot be negative",
                "set params.start_index to 0 or greater",
            )
        )

    column_key = ctx.column.strip() if isinstance(ctx.column, str) and ctx.column.strip() else f"params:{id(params)}"
    state_key = (ctx.table, column_key)
    state = _ORDERED_CHOICE_STATE.get(state_key)
    if state is None:
        selected_order = ctx.rng.choices(order_names, weights=order_weights, k=1)[0]
        sequence = orders[selected_order]
        if start_index >= len(sequence):
            raise ValueError(
                _generator_error(
                    location,
                    f"params.start_index={start_index} is outside selected order '{selected_order}' length {len(sequence)}",
                    "set params.start_index within the order length",
                )
            )
        state = {"sequence": sequence, "index": start_index, "move_weights": move_weights}
        _ORDERED_CHOICE_STATE[state_key] = state

    sequence = state["sequence"]
    state_move_weights = state["move_weights"]
    index = int(state["index"])
    value = sequence[index]
    step = ctx.rng.choices(range(len(state_move_weights)), weights=state_move_weights, k=1)[0]
    state["index"] = min(index + int(step), len(sequence) - 1)
    return value


@register("state_transition")
def gen_state_transition(params: Dict[str, Any], ctx: GenContext) -> Any:
    location = f"Table '{ctx.table}', generator 'state_transition'"

    entity_column_raw = params.get("entity_column")
    if not isinstance(entity_column_raw, str) or entity_column_raw.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                "params.entity_column is required",
                "set params.entity_column to a same-row source column and add it to depends_on",
            )
        )
    entity_column = entity_column_raw.strip()
    if entity_column not in ctx.row:
        raise ValueError(
            _generator_error(
                location,
                f"entity_column '{entity_column}' is not available in row context",
                "set depends_on to include the entity column so it generates first",
            )
        )

    column_key = ctx.column.strip() if isinstance(ctx.column, str) and ctx.column.strip() else f"params:{id(params)}"
    config_key = (ctx.table, column_key)
    config = _STATE_TRANSITION_CONFIG_STATE.get(config_key)
    if config is None:
        config = _build_state_transition_config(params, location=location)
        _STATE_TRANSITION_CONFIG_STATE[config_key] = config

    entity_identity = (type(ctx.row[entity_column]).__name__, repr(ctx.row[entity_column]))
    state_key = (ctx.table, column_key, entity_identity)
    state = _STATE_TRANSITION_ENTITY_STATE.get(state_key)
    if state is None:
        start_weights = config["start_weights"]
        if isinstance(start_weights, list):
            current_state = ctx.rng.choices(config["states"], weights=start_weights, k=1)[0]
        else:
            current_state = config["start_state"]
        min_dwell, max_dwell = _state_transition_dwell_bounds(config, current_state)
        state = {
            "current_state": current_state,
            "remaining": ctx.rng.randint(min_dwell, max_dwell),
        }
        _STATE_TRANSITION_ENTITY_STATE[state_key] = state

    current_state = state["current_state"]
    remaining = int(state["remaining"])
    if remaining <= 0:
        terminal_states = config["terminal_states"]
        if current_state in terminal_states:
            next_state = current_state
        else:
            transition = config["transitions"].get(current_state)
            if transition is None:
                raise ValueError(
                    _generator_error(
                        location,
                        f"current state '{current_state}' has no transition definition",
                        "configure transitions for every non-terminal state",
                    )
                )
            targets, weights = transition
            if not any(weight > 0 for weight in weights):
                raise ValueError(
                    _generator_error(
                        location,
                        f"current state '{current_state}' has no positive transition weights",
                        "set one or more outbound transition weights above zero",
                    )
                )
            next_state = ctx.rng.choices(targets, weights=weights, k=1)[0]
        current_state = next_state
        min_dwell, max_dwell = _state_transition_dwell_bounds(config, current_state)
        remaining = ctx.rng.randint(min_dwell, max_dwell)

    output_state = current_state
    state["current_state"] = current_state
    state["remaining"] = remaining - 1
    return output_state


def _coerce_derived_expression_result(value: Any, *, dtype: str, location: str) -> Any:
    target_dtype = dtype.strip().lower()
    if target_dtype == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype 'int'",
                    "return an integer result or cast explicitly with to_int(...)",
                )
            )
        return value
    if target_dtype in {"decimal", "float"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype '{target_dtype}'",
                    "return a numeric result or cast explicitly with to_decimal(...)",
                )
            )
        return float(value)
    if target_dtype == "text":
        if not isinstance(value, str):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype 'text'",
                    "return text directly or cast explicitly with to_text(...)",
                )
            )
        return value
    if target_dtype == "bool":
        if not isinstance(value, bool):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype 'bool'",
                    "return a boolean expression result or cast explicitly with to_bool(...)",
                )
            )
        return value
    if target_dtype == "date":
        if not is_iso_date_text(value):
            raise ValueError(
                _generator_error(
                    location,
                    "derived expression result is not a valid ISO date",
                    "return text in 'YYYY-MM-DD' format for date columns",
                )
            )
        return str(value).strip()
    if target_dtype == "datetime":
        if not is_iso_datetime_text(value):
            raise ValueError(
                _generator_error(
                    location,
                    "derived expression result is not a valid ISO datetime",
                    "return ISO datetime text (for example '2026-02-24T10:00:00Z')",
                )
            )
        return str(value).strip()
    return value


@register("derived_expr")
def gen_derived_expr(params: Dict[str, Any], ctx: GenContext) -> Any:
    location = f"Table '{ctx.table}', column '{ctx.column}', generator 'derived_expr'"
    expression_raw = params.get("expression")
    if not isinstance(expression_raw, str) or expression_raw.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                "params.expression is required",
                "set params.expression to a non-empty expression string",
            )
        )
    expression = expression_raw.strip()

    column_key = ctx.column.strip() if isinstance(ctx.column, str) and ctx.column.strip() else f"params:{id(params)}"
    state_key = (ctx.table, column_key)
    compiled = _DERIVED_EXPRESSION_STATE.get(state_key)
    if compiled is None or compiled.expression != expression:
        compiled = compile_derived_expression(expression, location=location)
        _DERIVED_EXPRESSION_STATE[state_key] = compiled

    value = evaluate_derived_expression(compiled, row=ctx.row, location=location)
    return _coerce_derived_expression_result(value, dtype=ctx.dtype, location=location)


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
