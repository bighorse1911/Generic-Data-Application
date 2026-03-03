from __future__ import annotations

from src.schema.validators.common import _scalar_identity


def validate_state_transition_generator(t, c, col_map) -> None:
    if c.generator == "state_transition":
        if c.dtype not in {"text", "int"}:
            raise ValueError(
                f"Table '{t.table_name}', column '{c.name}': generator 'state_transition' requires dtype text or int. "
                "Fix: change dtype to text/int or choose a generator compatible with this dtype."
            )
        params = c.params or {}
        location = f"Table '{t.table_name}', column '{c.name}': generator 'state_transition'"

        entity_col_raw = params.get("entity_column")
        if not isinstance(entity_col_raw, str) or entity_col_raw.strip() == "":
            raise ValueError(
                f"{location}: params.entity_column is required. "
                "Fix: set params.entity_column to an existing source column name."
            )
        entity_col = entity_col_raw.strip()
        if entity_col == c.name:
            raise ValueError(
                f"{location}: params.entity_column cannot reference the target column itself. "
                "Fix: choose a different source column for entity identity."
            )
        if entity_col not in col_map:
            raise ValueError(
                f"{location}: params.entity_column '{entity_col}' was not found. "
                "Fix: use an existing source column name."
            )
        depends_on = c.depends_on or []
        if entity_col not in depends_on:
            raise ValueError(
                f"{location}: requires depends_on to include '{entity_col}'. "
                "Fix: add the entity source column to depends_on so it generates first."
            )

        states_raw = params.get("states")
        if not isinstance(states_raw, list) or len(states_raw) == 0:
            raise ValueError(
                f"{location}: params.states must be a non-empty list. "
                "Fix: provide one or more allowed state values."
            )

        states: list[object] = []
        state_identities: set[tuple[str, str]] = set()
        for idx, raw_state in enumerate(states_raw):
            if isinstance(raw_state, (dict, list)) or isinstance(raw_state, bool):
                raise ValueError(
                    f"{location}: params.states[{idx}] must be a scalar text/int value. "
                    "Fix: use only string or integer states."
                )
            if c.dtype == "text":
                if not isinstance(raw_state, str) or raw_state.strip() == "":
                    raise ValueError(
                        f"{location}: params.states[{idx}] must be a non-empty string for dtype text. "
                        "Fix: use non-empty string states when dtype='text'."
                    )
                normalized_state: object = raw_state
            else:
                if not isinstance(raw_state, int):
                    raise ValueError(
                        f"{location}: params.states[{idx}] must be an integer for dtype int. "
                        "Fix: use integer states when dtype='int'."
                    )
                normalized_state = int(raw_state)
            identity = _scalar_identity(normalized_state)
            if identity in state_identities:
                raise ValueError(
                    f"{location}: params.states contains duplicate values. "
                    "Fix: list each state only once."
                )
            state_identities.add(identity)
            states.append(normalized_state)

        state_set = set(states)

        def _coerce_state_ref(
            raw_value: object,
            *,
            field_name: str,
            allow_int_string: bool,
        ) -> object:
            if c.dtype == "text":
                if not isinstance(raw_value, str):
                    raise ValueError(
                        f"{location}: {field_name} must reference text states. "
                        "Fix: use string state values declared in params.states."
                    )
                normalized = raw_value
            else:
                if isinstance(raw_value, bool):
                    raise ValueError(
                        f"{location}: {field_name} must reference integer states. "
                        "Fix: use integer state values declared in params.states."
                    )
                if isinstance(raw_value, int):
                    normalized = int(raw_value)
                elif allow_int_string and isinstance(raw_value, str) and raw_value.strip() != "":
                    try:
                        normalized = int(raw_value.strip())
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"{location}: {field_name} value '{raw_value}' is not a valid integer state. "
                            "Fix: use integer state values declared in params.states."
                        ) from exc
                else:
                    raise ValueError(
                        f"{location}: {field_name} must reference integer states. "
                        "Fix: use integer state values declared in params.states."
                    )
            if normalized not in state_set:
                raise ValueError(
                    f"{location}: {field_name} value '{normalized}' is not in params.states. "
                    "Fix: reference only states declared in params.states."
                )
            return normalized

        start_state_raw = params.get("start_state")
        start_weights_raw = params.get("start_weights")
        if start_state_raw is not None and start_weights_raw is not None:
            raise ValueError(
                f"{location}: params.start_state and params.start_weights cannot both be set. "
                "Fix: configure either a fixed start_state or weighted start_weights."
            )
        if start_state_raw is not None:
            _coerce_state_ref(
                start_state_raw,
                field_name="params.start_state",
                allow_int_string=False,
            )
        if start_weights_raw is not None:
            if not isinstance(start_weights_raw, dict) or len(start_weights_raw) == 0:
                raise ValueError(
                    f"{location}: params.start_weights must be a non-empty object when provided. "
                    "Fix: map each declared state to a numeric weight."
                )
            normalized_start_weights: dict[object, float] = {}
            for raw_key, raw_weight in start_weights_raw.items():
                state_key = _coerce_state_ref(
                    raw_key,
                    field_name="params.start_weights key",
                    allow_int_string=True,
                )
                if state_key in normalized_start_weights:
                    raise ValueError(
                        f"{location}: params.start_weights has duplicate keys after normalization. "
                        "Fix: include one unique key per state."
                    )
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.start_weights['{raw_key}'] must be numeric. "
                        "Fix: provide numeric non-negative start weights."
                    ) from exc
                if weight < 0:
                    raise ValueError(
                        f"{location}: params.start_weights['{raw_key}'] cannot be negative. "
                        "Fix: use non-negative start weights."
                    )
                normalized_start_weights[state_key] = weight
            if set(normalized_start_weights.keys()) != state_set:
                raise ValueError(
                    f"{location}: params.start_weights keys must exactly match params.states. "
                    "Fix: provide one start weight for each state and remove extras."
                )
            if not any(weight > 0 for weight in normalized_start_weights.values()):
                raise ValueError(
                    f"{location}: params.start_weights must include at least one value > 0. "
                    "Fix: set one or more start weights above zero."
                )

        terminal_states_raw = params.get("terminal_states", [])
        if not isinstance(terminal_states_raw, list):
            raise ValueError(
                f"{location}: params.terminal_states must be a list when provided. "
                "Fix: set params.terminal_states to a list of declared states or omit it."
            )
        terminal_states: set[object] = set()
        for idx, raw_terminal in enumerate(terminal_states_raw):
            terminal_state = _coerce_state_ref(
                raw_terminal,
                field_name=f"params.terminal_states[{idx}]",
                allow_int_string=False,
            )
            if terminal_state in terminal_states:
                raise ValueError(
                    f"{location}: params.terminal_states contains duplicate values. "
                    "Fix: list each terminal state only once."
                )
            terminal_states.add(terminal_state)

        dwell_min_raw = params.get("dwell_min", 1)
        dwell_max_raw = params.get("dwell_max", dwell_min_raw)
        try:
            dwell_min = int(dwell_min_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location}: params.dwell_min must be an integer. "
                "Fix: set params.dwell_min to 1 or greater."
            ) from exc
        try:
            dwell_max = int(dwell_max_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location}: params.dwell_max must be an integer. "
                "Fix: set params.dwell_max to an integer >= params.dwell_min."
            ) from exc
        if dwell_min < 1:
            raise ValueError(
                f"{location}: params.dwell_min must be >= 1. "
                "Fix: set params.dwell_min to 1 or greater."
            )
        if dwell_max < dwell_min:
            raise ValueError(
                f"{location}: params.dwell_max cannot be less than params.dwell_min. "
                "Fix: set params.dwell_max >= params.dwell_min."
            )

        dwell_by_state_raw = params.get("dwell_by_state")
        if dwell_by_state_raw is not None:
            if not isinstance(dwell_by_state_raw, dict):
                raise ValueError(
                    f"{location}: params.dwell_by_state must be an object when provided. "
                    "Fix: set params.dwell_by_state to a state->min/max object map."
                )
            seen_dwell_states: set[object] = set()
            for raw_key, raw_bounds in dwell_by_state_raw.items():
                dwell_state = _coerce_state_ref(
                    raw_key,
                    field_name="params.dwell_by_state key",
                    allow_int_string=True,
                )
                if dwell_state in seen_dwell_states:
                    raise ValueError(
                        f"{location}: params.dwell_by_state has duplicate keys after normalization. "
                        "Fix: include one per-state dwell override entry."
                    )
                seen_dwell_states.add(dwell_state)
                if not isinstance(raw_bounds, dict):
                    raise ValueError(
                        f"{location}: params.dwell_by_state['{raw_key}'] must be an object. "
                        "Fix: configure per-state min/max integer bounds."
                    )
                min_raw = raw_bounds.get("min", dwell_min)
                max_raw = raw_bounds.get("max", min_raw)
                try:
                    min_bound = int(min_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.dwell_by_state['{raw_key}'].min must be an integer. "
                        "Fix: set per-state min dwell to 1 or greater."
                    ) from exc
                try:
                    max_bound = int(max_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.dwell_by_state['{raw_key}'].max must be an integer. "
                        "Fix: set per-state max dwell to an integer >= min."
                    ) from exc
                if min_bound < 1:
                    raise ValueError(
                        f"{location}: params.dwell_by_state['{raw_key}'].min must be >= 1. "
                        "Fix: set per-state min dwell to 1 or greater."
                    )
                if max_bound < min_bound:
                    raise ValueError(
                        f"{location}: params.dwell_by_state['{raw_key}'].max cannot be less than min. "
                        "Fix: set per-state max dwell >= min."
                    )

        transitions_raw = params.get("transitions")
        if not isinstance(transitions_raw, dict) or len(transitions_raw) == 0:
            raise ValueError(
                f"{location}: params.transitions must be a non-empty object. "
                "Fix: set params.transitions like {'new': {'active': 1.0}}."
            )
        normalized_transitions: dict[object, dict[object, float]] = {}
        for raw_from, raw_targets in transitions_raw.items():
            from_state = _coerce_state_ref(
                raw_from,
                field_name="params.transitions key",
                allow_int_string=True,
            )
            if from_state in normalized_transitions:
                raise ValueError(
                    f"{location}: params.transitions has duplicate from-state keys after normalization. "
                    "Fix: include one unique from-state entry per declared state."
                )
            if not isinstance(raw_targets, dict) or len(raw_targets) == 0:
                raise ValueError(
                    f"{location}: params.transitions['{raw_from}'] must be a non-empty object. "
                    "Fix: configure one or more outbound transition weights."
                )
            normalized_targets: dict[object, float] = {}
            has_positive_weight = False
            for raw_to, raw_weight in raw_targets.items():
                to_state = _coerce_state_ref(
                    raw_to,
                    field_name=f"params.transitions['{raw_from}'] key",
                    allow_int_string=True,
                )
                if to_state == from_state:
                    raise ValueError(
                        f"{location}: params.transitions['{raw_from}'] cannot include self-transition '{raw_to}'. "
                        "Fix: remove self-transition edges and use dwell controls for state hold behavior."
                    )
                if to_state in normalized_targets:
                    raise ValueError(
                        f"{location}: params.transitions['{raw_from}'] has duplicate targets after normalization. "
                        "Fix: include each target state only once."
                    )
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.transitions['{raw_from}']['{raw_to}'] must be numeric. "
                        "Fix: use numeric non-negative transition weights."
                    ) from exc
                if weight < 0:
                    raise ValueError(
                        f"{location}: params.transitions['{raw_from}']['{raw_to}'] cannot be negative. "
                        "Fix: use non-negative transition weights."
                    )
                if weight > 0:
                    has_positive_weight = True
                normalized_targets[to_state] = weight
            if not has_positive_weight:
                raise ValueError(
                    f"{location}: params.transitions['{raw_from}'] must include at least one value > 0. "
                    "Fix: set one or more outbound transition weights above zero."
                )
            normalized_transitions[from_state] = normalized_targets

        for terminal_state in terminal_states:
            outbound = normalized_transitions.get(terminal_state)
            if outbound:
                raise ValueError(
                    f"{location}: terminal state '{terminal_state}' cannot define outbound transitions. "
                    "Fix: remove transition entries for terminal states."
                )

        for state in states:
            if state in terminal_states:
                continue
            if state not in normalized_transitions:
                raise ValueError(
                    f"{location}: non-terminal state '{state}' is missing transition weights. "
                    "Fix: add one or more outbound transition targets for every non-terminal state."
                )


__all__ = ["validate_state_transition_generator"]
