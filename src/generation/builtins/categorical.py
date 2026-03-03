from __future__ import annotations

from typing import Any, Dict

from src.generation.generator_common import (
    _generator_error,
    _is_scalar_json_value,
    _parse_positive_weight_list,
)
from src.generation.generator_state import _ORDERED_CHOICE_STATE
from src.generation.registry_core import GenContext, register
from src.project_paths import resolve_repo_path
from src.value_pools import load_csv_column, load_csv_column_by_match


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


__all__ = ["gen_choice_weighted", "gen_hierarchical_category", "gen_ordered_choice", "gen_sample_csv"]
