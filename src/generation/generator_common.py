from __future__ import annotations

from typing import Any, Dict


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
