from __future__ import annotations


def validate_numeric_generator_rules(
    table,
    column,
    *,
    parse_float_param,
    parse_int_param,
) -> None:
    if column.generator == "uniform_int":
        if column.dtype != "int":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'uniform_int' requires dtype int. "
                "Fix: set dtype='int' or use 'uniform_float'/'normal' for decimal-like values."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'uniform_int'"
        min_v = parse_int_param(
            params,
            "min",
            location=location,
            hint="set params.min to a whole-number lower bound",
            default=0,
        )
        max_v = parse_int_param(
            params,
            "max",
            location=location,
            hint="set params.max to a whole-number upper bound",
            default=100,
        )
        if min_v is not None and max_v is not None and min_v > max_v:
            raise ValueError(
                f"{location}: params.max cannot be less than params.min. "
                "Fix: set params.max >= params.min."
            )
    if column.generator == "uniform_float":
        if column.dtype not in {"float", "decimal"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'uniform_float' requires dtype decimal or legacy float. "
                "Fix: set dtype='decimal' for new numeric columns."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'uniform_float'"
        min_v = parse_float_param(
            params,
            "min",
            location=location,
            hint="set params.min to a numeric lower bound",
            default=0.0,
        )
        max_v = parse_float_param(
            params,
            "max",
            location=location,
            hint="set params.max to a numeric upper bound",
            default=1.0,
        )
        decimals = parse_int_param(
            params,
            "decimals",
            location=location,
            hint="set params.decimals to 0 or greater",
            default=3,
        )
        if decimals is not None and decimals < 0:
            raise ValueError(
                f"{location}: params.decimals must be >= 0. "
                "Fix: set params.decimals to 0 or greater."
            )
        if min_v is not None and max_v is not None and min_v > max_v:
            raise ValueError(
                f"{location}: params.max cannot be less than params.min. "
                "Fix: set params.max >= params.min."
            )
    if column.generator == "normal":
        if column.dtype not in {"int", "float", "decimal"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'normal' requires dtype int, decimal, or legacy float. "
                "Fix: change dtype to int/decimal or choose a text-compatible generator."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'normal'"
        parse_float_param(
            params,
            "mean",
            location=location,
            hint="set params.mean to a numeric average value",
            default=0.0,
        )
        has_stdev = "stdev" in params
        has_stddev = "stddev" in params
        if has_stdev and has_stddev:
            raise ValueError(
                f"{location}: params.stdev and params.stddev cannot both be set. "
                "Fix: provide only one standard deviation key."
            )
        stdev_key = "stddev" if has_stddev else "stdev"
        stdev = parse_float_param(
            params,
            stdev_key,
            location=location,
            hint=f"set params.{stdev_key} to a positive number",
            default=1.0,
        )
        if stdev is not None and stdev <= 0:
            raise ValueError(
                f"{location}: params.{stdev_key} must be > 0. "
                f"Fix: set params.{stdev_key} to a positive number."
            )
        decimals = parse_int_param(
            params,
            "decimals",
            location=location,
            hint="set params.decimals to 0 or greater",
            default=2,
        )
        if decimals is not None and decimals < 0:
            raise ValueError(
                f"{location}: params.decimals must be >= 0. "
                "Fix: set params.decimals to 0 or greater."
            )
        min_v = parse_float_param(
            params,
            "min",
            location=location,
            hint="set params.min to a numeric lower bound or omit it",
        )
        max_v = parse_float_param(
            params,
            "max",
            location=location,
            hint="set params.max to a numeric upper bound or omit it",
        )
        if min_v is not None and max_v is not None and min_v > max_v:
            raise ValueError(
                f"{location}: params.max cannot be less than params.min. "
                "Fix: set params.max >= params.min."
            )
    if column.generator == "lognormal":
        if column.dtype not in {"int", "float", "decimal"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'lognormal' requires dtype int, decimal, or legacy float. "
                "Fix: change dtype to int/decimal or choose a text-compatible generator."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'lognormal'"
        median = parse_float_param(
            params,
            "median",
            location=location,
            hint="set params.median to a positive number",
            default=50000.0,
        )
        sigma = parse_float_param(
            params,
            "sigma",
            location=location,
            hint="set params.sigma to a positive number",
            default=0.5,
        )
        if median is not None and median <= 0:
            raise ValueError(
                f"{location}: params.median must be > 0. "
                "Fix: set params.median to a positive number."
            )
        if sigma is not None and sigma <= 0:
            raise ValueError(
                f"{location}: params.sigma must be > 0. "
                "Fix: set params.sigma to a positive number."
            )
        decimals = parse_int_param(
            params,
            "decimals",
            location=location,
            hint="set params.decimals to 0 or greater",
            default=2,
        )
        if decimals is not None and decimals < 0:
            raise ValueError(
                f"{location}: params.decimals must be >= 0. "
                "Fix: set params.decimals to 0 or greater."
            )
        min_v = parse_float_param(
            params,
            "min",
            location=location,
            hint="set params.min to a numeric lower bound or omit it",
        )
        max_v = parse_float_param(
            params,
            "max",
            location=location,
            hint="set params.max to a numeric upper bound or omit it",
        )
        if min_v is not None and max_v is not None and min_v > max_v:
            raise ValueError(
                f"{location}: params.max cannot be less than params.min. "
                "Fix: set params.max >= params.min."
            )
    if column.generator == "choice_weighted":
        if column.dtype not in {"text", "int"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'choice_weighted' requires dtype text or int. "
                "Fix: change dtype to text/int or choose a generator compatible with this dtype."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'choice_weighted'"
        choices = params.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise ValueError(
                f"{location}: params.choices must be a non-empty list. "
                "Fix: provide one or more values in params.choices."
            )
        weights = params.get("weights")
        if weights is not None:
            if not isinstance(weights, list) or len(weights) != len(choices):
                raise ValueError(
                    f"{location}: params.weights must match params.choices length. "
                    "Fix: provide one numeric weight per choice or omit params.weights."
                )
            parsed_weights: list[float] = []
            for idx, weight in enumerate(weights):
                try:
                    weight_num = float(weight)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.weights[{idx}] must be numeric. "
                        "Fix: provide numeric weights (for example 0.2, 1, 3.5)."
                    ) from exc
                if weight_num < 0:
                    raise ValueError(
                        f"{location}: params.weights[{idx}] cannot be negative. "
                        "Fix: use weights >= 0 and keep at least one value > 0."
                    )
                parsed_weights.append(weight_num)
            if not any(w > 0 for w in parsed_weights):
                raise ValueError(
                    f"{location}: params.weights must include at least one value > 0. "
                    "Fix: set one or more weights above zero."
                )
    if column.generator == "ordered_choice":
        if column.dtype not in {"text", "int"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'ordered_choice' requires dtype text or int. "
                "Fix: change dtype to text/int or choose a generator compatible with this dtype."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'ordered_choice'"
        orders_raw = params.get("orders")
        if not isinstance(orders_raw, dict) or len(orders_raw) == 0:
            raise ValueError(
                f"{location}: params.orders must be a non-empty object. "
                "Fix: set params.orders to a mapping like {'A': ['one', 'two'], 'B': ['three', 'four']}."
            )

        normalized_orders: dict[str, list[object]] = {}
        for raw_name, raw_values in orders_raw.items():
            if not isinstance(raw_name, str) or raw_name.strip() == "":
                raise ValueError(
                    f"{location}: params.orders keys must be non-empty strings. "
                    "Fix: use order names like 'A' or 'OrderB' as object keys."
                )
            order_name = raw_name.strip()
            if order_name in normalized_orders:
                raise ValueError(
                    f"{location}: duplicate order key '{order_name}' after normalization. "
                    "Fix: use unique order names in params.orders."
                )
            if not isinstance(raw_values, list) or len(raw_values) == 0:
                raise ValueError(
                    f"{location}: params.orders['{order_name}'] must be a non-empty list. "
                    "Fix: provide one or more ordered values per order."
                )
            for idx, value in enumerate(raw_values):
                if isinstance(value, (dict, list)):
                    raise ValueError(
                        f"{location}: params.orders['{order_name}'][{idx}] must be a scalar value. "
                        "Fix: use string/number/bool/null values in order lists."
                    )
            normalized_orders[order_name] = raw_values

        order_names = list(normalized_orders.keys())
        order_weights_raw = params.get("order_weights")
        if order_weights_raw is not None:
            if not isinstance(order_weights_raw, dict):
                raise ValueError(
                    f"{location}: params.order_weights must be an object when provided. "
                    "Fix: set params.order_weights like {'A': 0.7, 'B': 0.3}."
                )
            missing_orders = [name for name in order_names if name not in order_weights_raw]
            extra_orders = [name for name in order_weights_raw.keys() if name not in normalized_orders]
            if missing_orders or extra_orders:
                missing_text = ", ".join(missing_orders) if missing_orders else "(none)"
                extra_text = ", ".join(str(name) for name in extra_orders) if extra_orders else "(none)"
                raise ValueError(
                    f"{location}: params.order_weights keys must exactly match params.orders keys (missing: {missing_text}; extra: {extra_text}). "
                    "Fix: add one weight per order and remove unknown order_weights keys."
                )
            parsed_order_weights: list[float] = []
            for order_name in order_names:
                raw_weight = order_weights_raw.get(order_name)
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.order_weights['{order_name}'] must be numeric. "
                        "Fix: provide numeric order weights (for example 0.2, 1, 3.5)."
                    ) from exc
                if weight < 0:
                    raise ValueError(
                        f"{location}: params.order_weights['{order_name}'] cannot be negative. "
                        "Fix: use non-negative order weights and keep at least one value > 0."
                    )
                parsed_order_weights.append(weight)
            if not any(weight > 0 for weight in parsed_order_weights):
                raise ValueError(
                    f"{location}: params.order_weights must include at least one value > 0. "
                    "Fix: set one or more order weights above zero."
                )

        move_weights_raw = params.get("move_weights", [0.0, 1.0])
        if not isinstance(move_weights_raw, list) or len(move_weights_raw) == 0:
            raise ValueError(
                f"{location}: params.move_weights must be a non-empty list. "
                "Fix: set params.move_weights to one or more numeric step weights."
            )
        parsed_move_weights: list[float] = []
        for idx, raw_weight in enumerate(move_weights_raw):
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{location}: params.move_weights[{idx}] must be numeric. "
                    "Fix: use numeric move weights (for example [0.1, 0.8, 0.1])."
                ) from exc
            if weight < 0:
                raise ValueError(
                    f"{location}: params.move_weights[{idx}] cannot be negative. "
                    "Fix: use non-negative move weights and keep at least one value > 0."
                )
            parsed_move_weights.append(weight)
        if not any(weight > 0 for weight in parsed_move_weights):
            raise ValueError(
                f"{location}: params.move_weights must include at least one value > 0. "
                "Fix: set one or more move weights above zero."
            )

        start_index_raw = params.get("start_index", 0)
        try:
            start_index = int(start_index_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location}: params.start_index must be an integer. "
                "Fix: set params.start_index to 0 or greater."
            ) from exc
        if start_index < 0:
            raise ValueError(
                f"{location}: params.start_index cannot be negative. "
                "Fix: set params.start_index to 0 or greater."
            )
        for order_name, order_values in normalized_orders.items():
            if start_index >= len(order_values):
                raise ValueError(
                    f"{location}: params.start_index={start_index} is outside order '{order_name}' length {len(order_values)}. "
                    "Fix: set params.start_index within every configured order length."
                )

__all__ = ["validate_numeric_generator_rules"]
