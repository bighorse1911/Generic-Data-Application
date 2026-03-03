from __future__ import annotations

from typing import Any, Dict

from src.generation.generator_common import _generator_error, _is_scalar_json_value
from src.generation.generator_state import _STATE_TRANSITION_CONFIG_STATE, _STATE_TRANSITION_ENTITY_STATE
from src.generation.registry_core import GenContext, register


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


__all__ = ["gen_state_transition"]
