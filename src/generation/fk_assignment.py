"""Foreign-key assignment helpers."""

from __future__ import annotations

import math
import random

from src.generation.common import _runtime_error
from src.schema_project_model import ForeignKeySpec

def _fk_lookup_identity(value: object) -> tuple[str, object]:
    if value is None:
        return ("none", None)
    if isinstance(value, bool):
        return ("bool", bool(value))
    if isinstance(value, int):
        return ("int", int(value))
    if isinstance(value, float) and value.is_integer():
        return ("int", int(value))
    if isinstance(value, str):
        text = value.strip()
        if text != "":
            try:
                return ("int", int(text))
            except (TypeError, ValueError):
                return ("str", value)
        return ("str", value)
    return (type(value).__name__, repr(value))


def _fk_selection_key_candidates(value: object) -> list[str]:
    keys: list[str] = []
    if value is None:
        keys.extend(["__NULL__", "null", "None"])
        return keys
    if isinstance(value, bool):
        keys.extend(["true" if value else "false", "True" if value else "False", "1" if value else "0"])
        return keys
    if isinstance(value, str):
        keys.append(value)
        stripped = value.strip()
        if stripped != value:
            keys.append(stripped)
        return keys
    if isinstance(value, float) and value.is_integer():
        keys.append(str(int(value)))
    keys.append(str(value))
    return keys


def _resolve_fk_parent_weight(
    value: object,
    *,
    weights: dict[str, float],
    default_weight: float,
) -> float:
    for key in _fk_selection_key_candidates(value):
        if key in weights:
            return weights[key]
    return default_weight


def _build_fk_parent_weights(
    fk: ForeignKeySpec,
    *,
    parent_rows: list[dict[str, object]],
    child_table: str,
) -> list[float] | None:
    raw_profile = fk.parent_selection
    if raw_profile is None:
        return None
    if not isinstance(raw_profile, dict):
        raise ValueError(
            _runtime_error(
                f"Table '{child_table}', FK column '{fk.child_column}'",
                "parent_selection must be an object when provided",
                "set parent_selection to an object with parent_attribute, weights, and optional default_weight",
            )
        )

    parent_attribute_raw = raw_profile.get("parent_attribute")
    if not isinstance(parent_attribute_raw, str) or parent_attribute_raw.strip() == "":
        raise ValueError(
            _runtime_error(
                f"Table '{child_table}', FK column '{fk.child_column}'",
                "parent_selection.parent_attribute is required",
                "set parent_selection.parent_attribute to an existing parent column name",
            )
        )
    parent_attribute = parent_attribute_raw.strip()

    weights_raw = raw_profile.get("weights")
    if not isinstance(weights_raw, dict) or len(weights_raw) == 0:
        raise ValueError(
            _runtime_error(
                f"Table '{child_table}', FK column '{fk.child_column}'",
                "parent_selection.weights must be a non-empty object",
                "set weights to a mapping of parent attribute values to non-negative numeric weights",
            )
        )

    normalized_weights: dict[str, float] = {}
    for raw_key, raw_weight in weights_raw.items():
        if not isinstance(raw_key, str) or raw_key.strip() == "":
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{fk.child_column}'",
                    "parent_selection.weights contains an empty or non-string key",
                    "use non-empty string keys in parent_selection.weights",
                )
            )
        key = raw_key.strip()
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{fk.child_column}'",
                    f"parent_selection.weights['{raw_key}'] must be numeric",
                    "use non-negative numeric values for parent_selection.weights",
                )
            ) from exc
        if (not math.isfinite(weight)) or weight < 0:
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{fk.child_column}'",
                    f"parent_selection.weights['{raw_key}'] must be a finite value >= 0",
                    "use non-negative finite numeric weights",
                )
            )
        normalized_weights[key] = weight

    default_weight_raw = raw_profile.get("default_weight", 1.0)
    try:
        default_weight = float(default_weight_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _runtime_error(
                f"Table '{child_table}', FK column '{fk.child_column}'",
                "parent_selection.default_weight must be numeric when provided",
                "set default_weight to a non-negative numeric value",
            )
        ) from exc
    if (not math.isfinite(default_weight)) or default_weight < 0:
        raise ValueError(
            _runtime_error(
                f"Table '{child_table}', FK column '{fk.child_column}'",
                "parent_selection.default_weight must be a finite value >= 0",
                "set default_weight to a non-negative finite numeric value",
            )
        )

    out: list[float] = []
    for parent_row in parent_rows:
        weight = _resolve_fk_parent_weight(
            parent_row.get(parent_attribute),
            weights=normalized_weights,
            default_weight=default_weight,
        )
        out.append(weight)
    return out


def _normalize_fk_child_count_distribution(
    fk: ForeignKeySpec,
    *,
    child_table: str,
) -> dict[str, object] | None:
    raw_profile = fk.child_count_distribution
    if raw_profile is None:
        return None
    location = f"Table '{child_table}', FK column '{fk.child_column}'"
    if not isinstance(raw_profile, dict):
        raise ValueError(
            _runtime_error(
                location,
                "child_count_distribution must be an object when provided",
                "set child_count_distribution to an object with type and optional shape parameters",
            )
        )

    dist_type_raw = raw_profile.get("type")
    if not isinstance(dist_type_raw, str) or dist_type_raw.strip() == "":
        raise ValueError(
            _runtime_error(
                location,
                "child_count_distribution.type is required",
                "set type to one of: uniform, poisson, zipf",
            )
        )
    dist_type = dist_type_raw.strip().lower()
    if dist_type not in {"uniform", "poisson", "zipf"}:
        raise ValueError(
            _runtime_error(
                location,
                f"unsupported child_count_distribution.type '{dist_type_raw}'",
                "set type to one of: uniform, poisson, zipf",
            )
        )

    normalized: dict[str, object] = {"type": dist_type}
    if dist_type == "poisson":
        lam_raw = raw_profile.get("lambda")
        if lam_raw is None:
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.lambda is required for type='poisson'",
                    "set lambda to a positive numeric value",
                )
            )
        if isinstance(lam_raw, bool):
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.lambda must be numeric",
                    "set lambda to a positive numeric value",
                )
            )
        try:
            lam = float(lam_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.lambda must be numeric",
                    "set lambda to a positive numeric value",
                )
            ) from exc
        if (not math.isfinite(lam)) or lam <= 0.0:
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.lambda must be a finite value > 0",
                    "set lambda to a positive numeric value",
                )
            )
        normalized["lambda"] = lam
    elif dist_type == "zipf":
        s_raw = raw_profile.get("s")
        if s_raw is None:
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.s is required for type='zipf'",
                    "set s to a positive numeric value (for example 1.2)",
                )
            )
        if isinstance(s_raw, bool):
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.s must be numeric",
                    "set s to a positive numeric value (for example 1.2)",
                )
            )
        try:
            s_value = float(s_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.s must be numeric",
                    "set s to a positive numeric value (for example 1.2)",
                )
            ) from exc
        if (not math.isfinite(s_value)) or s_value <= 0.0:
            raise ValueError(
                _runtime_error(
                    location,
                    "child_count_distribution.s must be a finite value > 0",
                    "set s to a positive numeric value (for example 1.2)",
                )
            )
        normalized["s"] = s_value
    return normalized


def _compile_fk_distribution_weights(
    distribution: dict[str, object] | None,
    *,
    extra_capacity: int,
    location: str,
) -> tuple[list[float] | None, list[float] | None]:
    if distribution is None or extra_capacity <= 0:
        return None, None

    dist_type = str(distribution.get("type"))
    extra_weights: list[float] = []
    if dist_type == "uniform":
        extra_weights = [1.0 for _ in range(extra_capacity + 1)]
    elif dist_type == "poisson":
        lam = float(distribution["lambda"])
        extra_weights = [1.0]
        for extra in range(1, extra_capacity + 1):
            extra_weights.append(extra_weights[-1] * lam / float(extra))
    elif dist_type == "zipf":
        s_value = float(distribution["s"])
        extra_weights = [1.0 / ((extra + 1) ** s_value) for extra in range(extra_capacity + 1)]
    else:
        raise ValueError(
            _runtime_error(
                location,
                f"unsupported child_count_distribution.type '{dist_type}'",
                "set type to one of: uniform, poisson, zipf",
            )
        )

    if not any((math.isfinite(weight) and weight > 0.0) for weight in extra_weights):
        raise ValueError(
            _runtime_error(
                location,
                "child_count_distribution produced no positive probability mass",
                "adjust distribution parameters so at least one child-count outcome has positive probability",
            )
        )

    tail_weights: list[float] = []
    running_tail = 0.0
    for extra in range(extra_capacity, 0, -1):
        running_tail += extra_weights[extra]
        tail_weights.append(running_tail)
    tail_weights.reverse()
    return extra_weights, tail_weights


def _sample_requested_fk_extras(
    rng: random.Random,
    *,
    parent_count: int,
    extra_capacity: int,
    extra_weights: list[float] | None,
) -> int:
    if parent_count <= 0 or extra_capacity <= 0:
        return 0
    if extra_weights is None:
        return sum(rng.randint(0, extra_capacity) for _ in range(parent_count))
    choices = list(range(extra_capacity + 1))
    total = 0
    for _ in range(parent_count):
        total += int(rng.choices(choices, weights=extra_weights, k=1)[0])
    return total


def _fk_parent_rows_and_ids(
    fk: ForeignKeySpec,
    *,
    results: dict[str, list[dict[str, object]]],
    child_table: str,
) -> tuple[list[dict[str, object]], list[int]]:
    parent_rows = results.get(fk.parent_table)
    if parent_rows is None:
        raise ValueError(
            _runtime_error(
                f"Table '{child_table}', FK column '{fk.child_column}'",
                f"parent table '{fk.parent_table}' rows are unavailable",
                "ensure parent tables are generated before child tables",
            )
        )
    parent_ids: list[int] = []
    for parent_index, parent_row in enumerate(parent_rows, start=1):
        parent_id_raw = parent_row.get(fk.parent_column)
        if isinstance(parent_id_raw, bool):
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{fk.child_column}'",
                    (
                        f"parent key '{fk.parent_table}.{fk.parent_column}' at row {parent_index} "
                        "is boolean and cannot be used as an int FK id"
                    ),
                    "ensure parent PK values are integer-like",
                )
            )
        try:
            parent_id = int(parent_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{fk.child_column}'",
                    (
                        f"parent key '{fk.parent_table}.{fk.parent_column}' at row {parent_index} "
                        f"is not integer-like (value={parent_id_raw!r})"
                    ),
                    "ensure parent PK values are generated and integer-like before FK assignment",
                )
            ) from exc
        parent_ids.append(parent_id)
    return parent_rows, parent_ids


def _allocate_fk_child_counts(
    rng: random.Random,
    *,
    parent_ids: list[int],
    min_children: int,
    max_children: int,
    total_children: int,
    location: str,
    parent_weights: list[float] | None = None,
    extra_level_weights: list[float] | None = None,
) -> list[int]:
    parent_n = len(parent_ids)
    if parent_n == 0:
        raise ValueError(
            _runtime_error(
                location,
                "cannot allocate FK children because parent table has zero rows",
                "generate one or more parent rows before assigning child foreign keys",
            )
        )

    min_total = parent_n * min_children
    max_total = parent_n * max_children

    if total_children < min_total:
        raise ValueError(
            _runtime_error(
                location,
                f"not enough rows to satisfy min_children (need >= {min_total}, have {total_children})",
                "increase child rows or lower min_children",
            )
        )
    if total_children > max_total:
        raise ValueError(
            _runtime_error(
                location,
                f"too many rows to satisfy max_children (need <= {max_total}, have {total_children})",
                "decrease child rows or raise max_children",
            )
        )
    if parent_weights is not None and len(parent_weights) != parent_n:
        raise ValueError(
            _runtime_error(
                location,
                "parent selection weight count does not match parent row count",
                "ensure parent_selection is defined against the current parent table rows",
            )
        )
    extra_capacity = max_children - min_children
    if extra_level_weights is not None and len(extra_level_weights) != extra_capacity:
        raise ValueError(
            _runtime_error(
                location,
                "child_count_distribution level-weight count does not match FK extra-capacity range",
                "set distribution shape parameters compatible with min_children/max_children bounds",
            )
        )

    counts = [min_children] * parent_n
    caps = [extra_capacity] * parent_n
    remaining = total_children - min_total

    while remaining > 0:
        eligible = [idx for idx, cap in enumerate(caps) if cap > 0]
        if not eligible:
            raise ValueError(
                _runtime_error(
                    location,
                    "cannot allocate remaining FK children within configured max_children bounds",
                    "increase max_children, reduce child rows, or adjust FK weighting",
                )
            )

        if parent_weights is None and extra_level_weights is None:
            chosen_idx = eligible[rng.randrange(len(eligible))]
        else:
            eligible_weights: list[float] = []
            has_positive_parent_weight = False
            for idx in eligible:
                base_weight = 1.0
                if parent_weights is not None:
                    base_weight = max(0.0, float(parent_weights[idx]))
                if base_weight > 0.0:
                    has_positive_parent_weight = True

                level_weight = 1.0
                if extra_level_weights is not None:
                    next_extra_level = (counts[idx] - min_children) + 1
                    level_weight = max(0.0, float(extra_level_weights[next_extra_level - 1]))

                eligible_weights.append(base_weight * level_weight)

            if not any(weight > 0.0 for weight in eligible_weights):
                if parent_weights is not None and not has_positive_parent_weight:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "parent_selection resolved to zero weight for all eligible parent rows",
                            "set positive weights/default_weight for cohorts that should receive additional child rows",
                        )
                    )
                if extra_level_weights is not None:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "child_count_distribution resolved to zero weight for all eligible parent rows at the current extra-child level",
                            "adjust distribution parameters or widen max_children so additional children remain allocatable",
                        )
                    )
                raise ValueError(
                    _runtime_error(
                        location,
                        "cannot allocate remaining FK children because all eligible parent rows have zero combined allocation weight",
                        "increase positive parent-selection weights or relax FK cardinality settings",
                    )
                )
            chosen_idx = rng.choices(eligible, weights=eligible_weights, k=1)[0]

        counts[chosen_idx] += 1
        caps[chosen_idx] -= 1
        remaining -= 1

    return counts


__all__ = ["_fk_lookup_identity", "_fk_selection_key_candidates", "_resolve_fk_parent_weight", "_build_fk_parent_weights", "_normalize_fk_child_count_distribution", "_compile_fk_distribution_weights", "_sample_requested_fk_extras", "_fk_parent_rows_and_ids", "_allocate_fk_child_counts"]
