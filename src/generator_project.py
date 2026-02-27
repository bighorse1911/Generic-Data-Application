import csv
import hashlib
import logging
import math
import random
import re
from datetime import date, datetime, timedelta, timezone
from typing import Callable
from src.generators import GenContext, get_generator, reset_runtime_generator_state
from src.locale_identity import LOCALE_IDENTITY_PACKS
from src.locale_identity import SUPPORTED_LOCALE_IDENTITY_SLOTS
from src.project_paths import resolve_repo_path
from src.project_paths import to_repo_relative_path
from src.schema_project_model import (
    SchemaProject,
    TableSpec,
    ColumnSpec,
    ForeignKeySpec,
    correlation_cholesky_lower,
    validate_project,
)

logger = logging.getLogger("generator_project")


def _runtime_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _stable_subseed(base_seed: int, name: str) -> int:
    """
    Deterministically derive a per-table/per-feature seed from base_seed and a string name.
    Avoids Python's built-in hash() which is randomized between runs.
    """
    h = hashlib.sha256(f"{base_seed}:{name}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _iso_date(d: date) -> str:
    return d.isoformat()


def _iso_datetime(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse_iso_date_value(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("not a date string")
    return date.fromisoformat(value.strip())


def _parse_iso_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip() != "":
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("not a datetime string")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _parse_child_temporal_or_none(value: object, *, dtype: str) -> object | None:
    if value is None:
        return None
    try:
        if dtype == "date":
            return _parse_iso_date_value(value)
        return _parse_iso_datetime_value(value)
    except Exception:
        return None


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


def _compile_timeline_constraints(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    raw_rules = project.timeline_constraints
    if not raw_rules:
        return {}

    table_map = {table.table_name: table for table in project.tables}
    fk_parent_pk_by_edge: dict[tuple[str, str, str], str] = {}
    for fk in project.foreign_keys:
        fk_parent_pk_by_edge[(fk.child_table, fk.child_column, fk.parent_table)] = fk.parent_column

    compiled: dict[str, list[dict[str, object]]] = {}
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            continue
        child_table = str(raw_rule.get("child_table", "")).strip()
        child_column = str(raw_rule.get("child_column", "")).strip()
        if child_table == "" or child_column == "":
            continue

        table = table_map.get(child_table)
        if table is None:
            continue
        child_dtype: str | None = None
        for column in table.columns:
            if column.name == child_column:
                child_dtype = column.dtype
                break
        if child_dtype not in {"date", "datetime"}:
            continue

        mode = str(raw_rule.get("mode", "enforce")).strip().lower()
        if mode != "enforce":
            continue

        references_raw = raw_rule.get("references")
        if not isinstance(references_raw, list) or len(references_raw) == 0:
            continue

        rule_id_raw = raw_rule.get("rule_id")
        if isinstance(rule_id_raw, str) and rule_id_raw.strip() != "":
            rule_id = rule_id_raw.strip()
        else:
            rule_id = f"rule_{index + 1}"

        compiled_references: list[dict[str, object]] = []
        for ref_index, raw_reference in enumerate(references_raw):
            if not isinstance(raw_reference, dict):
                continue
            parent_table = str(raw_reference.get("parent_table", "")).strip()
            parent_column = str(raw_reference.get("parent_column", "")).strip()
            via_child_fk = str(raw_reference.get("via_child_fk", "")).strip()
            direction = str(raw_reference.get("direction", "")).strip().lower()
            parent_pk_column = fk_parent_pk_by_edge.get((child_table, via_child_fk, parent_table))
            if (
                parent_table == ""
                or parent_column == ""
                or via_child_fk == ""
                or direction not in {"after", "before"}
                or not isinstance(parent_pk_column, str)
                or parent_pk_column.strip() == ""
            ):
                continue

            if child_dtype == "date":
                try:
                    min_offset = int(raw_reference.get("min_days", 0))
                    max_offset = int(raw_reference.get("max_days", min_offset))
                except (TypeError, ValueError):
                    continue
            else:
                try:
                    min_offset = int(raw_reference.get("min_seconds", 0))
                    max_offset = int(raw_reference.get("max_seconds", min_offset))
                except (TypeError, ValueError):
                    continue
            if min_offset < 0 or max_offset < min_offset:
                continue

            compiled_references.append(
                {
                    "reference_index": ref_index,
                    "parent_table": parent_table,
                    "parent_column": parent_column,
                    "parent_pk_column": parent_pk_column,
                    "via_child_fk": via_child_fk,
                    "direction": direction,
                    "min_offset": min_offset,
                    "max_offset": max_offset,
                }
            )

        if not compiled_references:
            continue

        compiled.setdefault(child_table, []).append(
            {
                "rule_index": index,
                "rule_id": rule_id,
                "child_column": child_column,
                "dtype": child_dtype,
                "references": compiled_references,
            }
        )

    return compiled


def _build_parent_lookup(
    parent_rows: list[dict[str, object]],
    *,
    parent_table: str,
    parent_pk_column: str,
) -> dict[tuple[str, object], dict[str, object]]:
    lookup: dict[tuple[str, object], dict[str, object]] = {}
    for idx, row in enumerate(parent_rows, start=1):
        key_raw = row.get(parent_pk_column)
        if key_raw is None:
            raise ValueError(
                _runtime_error(
                    f"Table '{parent_table}', row {idx}, column '{parent_pk_column}'",
                    "parent lookup key is null during DG03 timeline enforcement",
                    "ensure parent PK values are generated and non-null before timeline enforcement",
                )
            )
        lookup[_fk_lookup_identity(key_raw)] = row
    return lookup


def _enforce_table_timeline_constraints(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    results: dict[str, list[dict[str, object]]],
    compiled_constraints: dict[str, list[dict[str, object]]],
) -> None:
    if not rows:
        return
    rules = compiled_constraints.get(table.table_name, [])
    if not rules:
        return

    parent_lookup_cache: dict[tuple[str, str], dict[tuple[str, object], dict[str, object]]] = {}

    for rule in rules:
        child_column = str(rule.get("child_column"))
        dtype = str(rule.get("dtype"))
        rule_id = str(rule.get("rule_id"))
        references = rule.get("references")
        if dtype not in {"date", "datetime"} or not isinstance(references, list) or not references:
            continue

        for row_index, row in enumerate(rows, start=1):
            row_location = f"Table '{table.table_name}', row {row_index}, column '{child_column}'"

            lower_bound: object | None = None
            upper_bound: object | None = None

            for raw_reference in references:
                if not isinstance(raw_reference, dict):
                    continue
                parent_table = str(raw_reference.get("parent_table"))
                parent_column = str(raw_reference.get("parent_column"))
                parent_pk_column = str(raw_reference.get("parent_pk_column"))
                via_child_fk = str(raw_reference.get("via_child_fk"))
                direction = str(raw_reference.get("direction")).lower()
                min_offset = int(raw_reference.get("min_offset", 0))
                max_offset = int(raw_reference.get("max_offset", min_offset))

                parent_rows = results.get(parent_table)
                if parent_rows is None:
                    raise ValueError(
                        _runtime_error(
                            row_location,
                            f"parent table '{parent_table}' rows are unavailable for DG03 timeline enforcement",
                            "ensure parent tables are generated before constrained child tables",
                        )
                    )

                cache_key = (parent_table, parent_pk_column)
                if cache_key not in parent_lookup_cache:
                    parent_lookup_cache[cache_key] = _build_parent_lookup(
                        parent_rows,
                        parent_table=parent_table,
                        parent_pk_column=parent_pk_column,
                    )
                parent_lookup = parent_lookup_cache[cache_key]

                fk_value_raw = row.get(via_child_fk)
                if fk_value_raw is None:
                    raise ValueError(
                        _runtime_error(
                            row_location,
                            f"child FK '{via_child_fk}' is null and cannot resolve parent '{parent_table}'",
                            "ensure FK assignment occurs before DG03 timeline enforcement",
                        )
                    )
                parent_row = parent_lookup.get(_fk_lookup_identity(fk_value_raw))
                if parent_row is None:
                    raise ValueError(
                        _runtime_error(
                            row_location,
                            (
                                f"could not resolve parent row in '{parent_table}' via "
                                f"child FK '{via_child_fk}' value '{fk_value_raw}'"
                            ),
                            "ensure FK values map to existing parent keys before DG03 timeline enforcement",
                        )
                    )

                parent_value_raw = parent_row.get(parent_column)
                if dtype == "date":
                    try:
                        parent_value = _parse_iso_date_value(parent_value_raw)
                    except Exception as exc:
                        raise ValueError(
                            _runtime_error(
                                row_location,
                                (
                                    f"parent value '{parent_table}.{parent_column}' is not a valid ISO date "
                                    f"(value={parent_value_raw!r})"
                                ),
                                "fix parent temporal values to valid 'YYYY-MM-DD' dates",
                            )
                        ) from exc
                    if direction == "after":
                        reference_lower = parent_value + timedelta(days=min_offset)
                        reference_upper = parent_value + timedelta(days=max_offset)
                    else:
                        reference_lower = parent_value - timedelta(days=max_offset)
                        reference_upper = parent_value - timedelta(days=min_offset)
                else:
                    try:
                        parent_value = _parse_iso_datetime_value(parent_value_raw)
                    except Exception as exc:
                        raise ValueError(
                            _runtime_error(
                                row_location,
                                (
                                    f"parent value '{parent_table}.{parent_column}' is not a valid ISO datetime "
                                    f"(value={parent_value_raw!r})"
                                ),
                                "fix parent temporal values to valid ISO datetimes with UTC-compatible timezone",
                            )
                        ) from exc
                    if direction == "after":
                        reference_lower = parent_value + timedelta(seconds=min_offset)
                        reference_upper = parent_value + timedelta(seconds=max_offset)
                    else:
                        reference_lower = parent_value - timedelta(seconds=max_offset)
                        reference_upper = parent_value - timedelta(seconds=min_offset)

                if lower_bound is None or reference_lower > lower_bound:
                    lower_bound = reference_lower
                if upper_bound is None or reference_upper < upper_bound:
                    upper_bound = reference_upper

            if lower_bound is None or upper_bound is None:
                continue
            if lower_bound > upper_bound:
                raise ValueError(
                    _runtime_error(
                        row_location,
                        f"timeline interval intersection is empty for DG03 rule '{rule_id}'",
                        "adjust DG03 direction/min/max offsets so parent-derived intervals overlap",
                    )
                )

            child_value_raw = row.get(child_column)
            child_value = _parse_child_temporal_or_none(child_value_raw, dtype=dtype)

            if child_value is not None and lower_bound <= child_value <= upper_bound:
                continue

            if child_value is None or child_value < lower_bound:
                replacement = lower_bound
            elif child_value > upper_bound:
                replacement = upper_bound
            else:
                replacement = lower_bound

            if dtype == "date":
                row[child_column] = _iso_date(replacement)
            else:
                row[child_column] = _iso_datetime(replacement)


def _profile_rate_triggered(rng: random.Random, rate: float) -> bool:
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return rng.random() < rate


def _profile_clamp_probability(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def _profile_scalar_identity(value: object) -> tuple[str, str]:
    return (type(value).__name__, repr(value))


def _profile_matches_where(
    row: dict[str, object],
    where_predicates: list[tuple[str, set[tuple[str, str]]]],
) -> bool:
    for column_name, allowed_values in where_predicates:
        marker = _profile_scalar_identity(row.get(column_name))
        if marker not in allowed_values:
            return False
    return True


def _default_format_error_value(
    *,
    dtype: str,
    profile_id: str,
) -> str:
    if dtype == "date":
        return f"INVALID_DATE_{profile_id}"
    if dtype == "datetime":
        return f"INVALID_DATETIME_{profile_id}"
    if dtype in {"int", "float", "decimal"}:
        return f"INVALID_NUMERIC_{profile_id}"
    if dtype == "bool":
        return f"INVALID_BOOL_{profile_id}"
    return f"INVALID_FORMAT_{profile_id}"


def _compile_data_quality_profiles(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    raw_profiles = project.data_quality_profiles
    if not raw_profiles:
        return {}

    table_map = {table.table_name: table for table in project.tables}

    def _parse_probability(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be numeric",
                    hint,
                )
            ) from exc
        if (not math.isfinite(parsed)) or parsed < 0.0 or parsed > 1.0:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be between 0 and 1",
                    hint,
                )
            )
        return parsed

    def _parse_non_negative_float(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be numeric",
                    hint,
                )
            ) from exc
        if (not math.isfinite(parsed)) or parsed < 0.0:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be a finite value >= 0",
                    hint,
                )
            )
        return parsed

    def _parse_int(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> int:
        if isinstance(value, bool):
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be an integer",
                    hint,
                )
            )
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be an integer",
                    hint,
                )
            ) from exc

    compiled: dict[str, list[dict[str, object]]] = {}
    for profile_index, raw_profile in enumerate(raw_profiles):
        location = f"Project data_quality_profiles[{profile_index}]"
        if not isinstance(raw_profile, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "profile must be an object",
                    "set each data_quality_profiles item to a JSON object",
                )
            )

        profile_id_raw = raw_profile.get("profile_id")
        if isinstance(profile_id_raw, str) and profile_id_raw.strip() != "":
            profile_id = profile_id_raw.strip()
        else:
            profile_id = f"profile_{profile_index + 1}"

        table_name = str(raw_profile.get("table", "")).strip()
        if table_name == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "table is required",
                    "set table to an existing table name",
                )
            )
        table = table_map.get(table_name)
        if table is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"table '{table_name}' was not found",
                    "use an existing table name for this DG06 profile",
                )
            )
        table_cols = {column.name: column for column in table.columns}

        column_name = str(raw_profile.get("column", "")).strip()
        if column_name == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "column is required",
                    "set column to an existing target column name",
                )
            )
        column = table_cols.get(column_name)
        if column is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"column '{column_name}' was not found on table '{table_name}'",
                    "use an existing table column for this DG06 profile",
                )
            )

        where_predicates: list[tuple[str, set[tuple[str, str]]]] = []
        where_raw = raw_profile.get("where")
        if where_raw is not None:
            if not isinstance(where_raw, dict):
                raise ValueError(
                    _runtime_error(
                        location,
                        "where must be an object when provided",
                        "set where to an object mapping columns to scalar value(s) or remove where",
                    )
                )
            for where_key_raw, where_values_raw in where_raw.items():
                if not isinstance(where_key_raw, str) or where_key_raw.strip() == "":
                    raise ValueError(
                        _runtime_error(
                            location,
                            "where contains an empty or non-string column key",
                            "use non-empty table column names as where keys",
                        )
                    )
                where_column = where_key_raw.strip()
                if where_column not in table_cols:
                    raise ValueError(
                        _runtime_error(
                            location,
                            f"where column '{where_column}' was not found on table '{table_name}'",
                            "use existing table columns in where predicates",
                        )
                    )
                if isinstance(where_values_raw, list):
                    if len(where_values_raw) == 0:
                        raise ValueError(
                            _runtime_error(
                                location,
                                f"where['{where_key_raw}'] cannot be an empty list",
                                "provide one or more scalar values in each where list",
                            )
                        )
                    match_values = where_values_raw
                else:
                    match_values = [where_values_raw]
                allowed = {_profile_scalar_identity(value) for value in match_values}
                where_predicates.append((where_column, allowed))

        kind = str(raw_profile.get("kind", "")).strip().lower()
        if kind == "missingness":
            mechanism = str(raw_profile.get("mechanism", "")).strip().lower()
            base_rate = _parse_probability(
                raw_profile.get("base_rate"),
                location=location,
                field_name="base_rate",
                hint="set base_rate to a numeric value between 0 and 1",
            )

            driver_column: str | None = None
            if mechanism == "mcar":
                driver_column = None
            elif mechanism == "mar":
                driver_column = str(raw_profile.get("driver_column", "")).strip()
                if driver_column == "":
                    raise ValueError(
                        _runtime_error(
                            location,
                            "driver_column is required for mechanism 'mar'",
                            "set driver_column to an existing source column name",
                        )
                    )
                if driver_column not in table_cols:
                    raise ValueError(
                        _runtime_error(
                            location,
                            f"driver_column '{driver_column}' was not found on table '{table_name}'",
                            "use an existing table column for driver_column",
                        )
                    )
            elif mechanism == "mnar":
                driver_column = column_name
            else:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"unsupported missingness mechanism '{mechanism}'",
                        "set mechanism to 'mcar', 'mar', or 'mnar'",
                    )
                )

            weights_raw = raw_profile.get("value_weights", {})
            if not isinstance(weights_raw, dict):
                raise ValueError(
                    _runtime_error(
                        location,
                        "value_weights must be an object when provided",
                        "set value_weights to a mapping of source values to non-negative weights",
                    )
                )
            normalized_weights: dict[str, float] = {}
            for raw_key, raw_weight in weights_raw.items():
                if not isinstance(raw_key, str) or raw_key.strip() == "":
                    raise ValueError(
                        _runtime_error(
                            location,
                            "value_weights contains an empty or non-string key",
                            "use non-empty string keys in value_weights",
                        )
                    )
                key = raw_key.strip()
                normalized_weights[key] = _parse_non_negative_float(
                    raw_weight,
                    location=location,
                    field_name=f"value_weights['{raw_key}']",
                    hint="use non-negative finite numeric weights",
                )
            default_weight = _parse_non_negative_float(
                raw_profile.get("default_weight", 1.0),
                location=location,
                field_name="default_weight",
                hint="set default_weight to a non-negative finite numeric value",
            )

            compiled_profile = {
                "profile_index": profile_index,
                "profile_id": profile_id,
                "table": table_name,
                "column": column_name,
                "dtype": column.dtype,
                "kind": "missingness",
                "where": where_predicates,
                "mechanism": mechanism,
                "base_rate": base_rate,
                "driver_column": driver_column,
                "value_weights": normalized_weights,
                "default_weight": default_weight,
            }
        elif kind == "quality_issue":
            issue_type = str(raw_profile.get("issue_type", "")).strip().lower()
            if issue_type not in {"format_error", "stale_value", "drift"}:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"unsupported issue_type '{issue_type}'",
                        "set issue_type to 'format_error', 'stale_value', or 'drift'",
                    )
                )
            rate = _parse_probability(
                raw_profile.get("rate"),
                location=location,
                field_name="rate",
                hint="set rate to a numeric value between 0 and 1",
            )
            compiled_profile = {
                "profile_index": profile_index,
                "profile_id": profile_id,
                "table": table_name,
                "column": column_name,
                "dtype": column.dtype,
                "kind": "quality_issue",
                "where": where_predicates,
                "issue_type": issue_type,
                "rate": rate,
            }
            if issue_type == "format_error":
                replacement_raw = raw_profile.get("replacement")
                replacement: str | None = None
                if isinstance(replacement_raw, str) and replacement_raw.strip() != "":
                    replacement = replacement_raw
                compiled_profile["replacement"] = replacement
            elif issue_type == "stale_value":
                lag_rows = _parse_int(
                    raw_profile.get("lag_rows", 1),
                    location=location,
                    field_name="lag_rows",
                    hint="set lag_rows to an integer >= 1",
                )
                if lag_rows < 1:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "lag_rows must be >= 1",
                            "set lag_rows to 1 or greater",
                        )
                    )
                compiled_profile["lag_rows"] = lag_rows
            else:
                if column.dtype not in {"int", "float", "decimal", "date", "datetime"}:
                    raise ValueError(
                        _runtime_error(
                            location,
                            f"drift does not support dtype '{column.dtype}'",
                            "target drift profiles to int/float/decimal/date/datetime columns",
                        )
                    )
                step_raw = raw_profile.get("step")
                if step_raw is None:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "drift.step is required",
                            "set step to a non-zero numeric value (or integer days/seconds for date/datetime)",
                        )
                    )
                if column.dtype in {"date", "datetime"}:
                    step = _parse_int(
                        step_raw,
                        location=location,
                        field_name="drift.step",
                        hint="set drift.step to a non-zero integer number of days/seconds",
                    )
                    if step == 0:
                        raise ValueError(
                            _runtime_error(
                                location,
                                "drift.step cannot be zero",
                                "set drift.step to a non-zero integer number of days/seconds",
                            )
                        )
                else:
                    try:
                        step = float(step_raw)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            _runtime_error(
                                location,
                                "drift.step must be numeric",
                                "set drift.step to a non-zero numeric drift increment",
                            )
                        ) from exc
                    if (not math.isfinite(step)) or step == 0.0:
                        raise ValueError(
                            _runtime_error(
                                location,
                                "drift.step must be a non-zero finite numeric value",
                                "set drift.step to a non-zero numeric drift increment",
                            )
                        )
                start_index = _parse_int(
                    raw_profile.get("start_index", 1),
                    location=location,
                    field_name="start_index",
                    hint="set start_index to an integer >= 1",
                )
                if start_index < 1:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "start_index must be >= 1",
                            "set start_index to 1 or greater",
                        )
                    )
                compiled_profile["step"] = step
                compiled_profile["start_index"] = start_index
        else:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported kind '{kind}'",
                    "set kind to 'missingness' or 'quality_issue'",
                )
            )

        compiled.setdefault(table_name, []).append(compiled_profile)

    return compiled


def _apply_table_data_quality_profiles(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    project_seed: int,
    compiled_profiles: dict[str, list[dict[str, object]]],
) -> None:
    if not rows:
        return
    profiles = compiled_profiles.get(table.table_name, [])
    if not profiles:
        return

    for profile in profiles:
        profile_id = str(profile.get("profile_id", "profile"))
        profile_index = int(profile.get("profile_index", 0))
        column_name = str(profile.get("column", ""))
        dtype = str(profile.get("dtype", ""))
        where_predicates = profile.get("where")
        if not isinstance(where_predicates, list):
            where_predicates = []
        profile_rng = random.Random(
            _stable_subseed(project_seed, f"dg06:{table.table_name}:{profile_id}:{profile_index}")
        )

        kind = str(profile.get("kind", ""))
        if kind == "missingness":
            mechanism = str(profile.get("mechanism", ""))
            base_rate = float(profile.get("base_rate", 0.0))
            driver_column_raw = profile.get("driver_column")
            driver_column = str(driver_column_raw) if driver_column_raw is not None else None
            value_weights = profile.get("value_weights")
            if not isinstance(value_weights, dict):
                value_weights = {}
            normalized_weights = {
                str(key): float(value)
                for key, value in value_weights.items()
            }
            default_weight = float(profile.get("default_weight", 1.0))

            for row in rows:
                if where_predicates and not _profile_matches_where(row, where_predicates):
                    continue
                if row.get(column_name) is None:
                    continue

                effective_rate = base_rate
                if mechanism in {"mar", "mnar"}:
                    source_column = driver_column if mechanism == "mar" else column_name
                    source_value = row.get(source_column) if source_column else row.get(column_name)
                    weight = _resolve_fk_parent_weight(
                        source_value,
                        weights=normalized_weights,
                        default_weight=default_weight,
                    )
                    effective_rate = _profile_clamp_probability(base_rate * weight)
                if _profile_rate_triggered(profile_rng, effective_rate):
                    row[column_name] = None

        elif kind == "quality_issue":
            issue_type = str(profile.get("issue_type", ""))
            rate = float(profile.get("rate", 0.0))
            if issue_type == "format_error":
                replacement_raw = profile.get("replacement")
                replacement = (
                    str(replacement_raw)
                    if isinstance(replacement_raw, str) and replacement_raw.strip() != ""
                    else _default_format_error_value(dtype=dtype, profile_id=profile_id)
                )
                for row in rows:
                    if where_predicates and not _profile_matches_where(row, where_predicates):
                        continue
                    if row.get(column_name) is None:
                        continue
                    if _profile_rate_triggered(profile_rng, rate):
                        row[column_name] = replacement

            elif issue_type == "stale_value":
                lag_rows = int(profile.get("lag_rows", 1))
                if lag_rows < 1:
                    continue
                baseline_values = [row.get(column_name) for row in rows]
                for row_index, row in enumerate(rows):
                    if row_index < lag_rows:
                        continue
                    if where_predicates and not _profile_matches_where(row, where_predicates):
                        continue
                    if not _profile_rate_triggered(profile_rng, rate):
                        continue
                    stale_value = baseline_values[row_index - lag_rows]
                    if stale_value is None:
                        continue
                    row[column_name] = stale_value

            elif issue_type == "drift":
                step = profile.get("step")
                start_index = int(profile.get("start_index", 1))
                for row_index, row in enumerate(rows, start=1):
                    if row_index < start_index:
                        continue
                    if where_predicates and not _profile_matches_where(row, where_predicates):
                        continue
                    if not _profile_rate_triggered(profile_rng, rate):
                        continue
                    current_value = row.get(column_name)
                    if current_value is None:
                        continue
                    progress = row_index - start_index + 1
                    row_location = f"Table '{table.table_name}', row {row_index}, column '{column_name}'"

                    if dtype == "int":
                        try:
                            base_value = int(current_value)
                            delta = float(step) * float(progress)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected integer-like value but found {current_value!r}",
                                    "ensure drift targets generated int values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = int(round(base_value + delta))
                    elif dtype in {"float", "decimal"}:
                        try:
                            base_value = float(current_value)
                            delta = float(step) * float(progress)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected numeric value but found {current_value!r}",
                                    "ensure drift targets generated numeric values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = float(base_value + delta)
                    elif dtype == "date":
                        try:
                            base_value = _parse_iso_date_value(current_value)
                            delta_days = int(step) * progress
                        except Exception as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected ISO date value but found {current_value!r}",
                                    "ensure drift targets parseable ISO date values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = _iso_date(base_value + timedelta(days=delta_days))
                    elif dtype == "datetime":
                        try:
                            base_value = _parse_iso_datetime_value(current_value)
                            delta_seconds = int(step) * progress
                        except Exception as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected ISO datetime value but found {current_value!r}",
                                    "ensure drift targets parseable ISO datetime values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = _iso_datetime(base_value + timedelta(seconds=delta_seconds))
                    else:
                        raise ValueError(
                            _runtime_error(
                                row_location,
                                f"DG06 drift does not support dtype '{dtype}'",
                                "target drift profiles to int/float/decimal/date/datetime columns",
                            )
                        )


def _normalize_locale_identity_columns(
    raw_columns: object,
    *,
    location: str,
    table_name: str,
    table_columns: dict[str, ColumnSpec],
) -> dict[str, str]:
    if not isinstance(raw_columns, dict) or len(raw_columns) == 0:
        raise ValueError(
            _runtime_error(
                location,
                "columns must be a non-empty object",
                "set columns to a mapping of DG09 slots to existing table columns",
            )
        )

    allowed_slots = set(SUPPORTED_LOCALE_IDENTITY_SLOTS)
    normalized: dict[str, str] = {}
    for raw_slot, raw_column in raw_columns.items():
        if not isinstance(raw_slot, str) or raw_slot.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "columns contains an empty or non-string slot key",
                    f"use one or more supported slots: {', '.join(sorted(allowed_slots))}",
                )
            )
        slot = raw_slot.strip()
        if slot not in allowed_slots:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported columns slot '{raw_slot}'",
                    f"use one of: {', '.join(sorted(allowed_slots))}",
                )
            )
        if slot in normalized:
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns has duplicate slot '{slot}' after normalization",
                    "list each DG09 slot once",
                )
            )
        if not isinstance(raw_column, str) or raw_column.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns['{raw_slot}'] must be a non-empty string column name",
                    "map each slot to an existing table column",
                )
            )
        column_name = raw_column.strip()
        column = table_columns.get(column_name)
        if column is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns['{raw_slot}'] column '{column_name}' was not found on table '{table_name}'",
                    "map each slot to an existing column on the configured table",
                )
            )
        if column.primary_key:
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns['{raw_slot}'] cannot target primary key column '{column_name}'",
                    "target non-primary-key columns for DG09 locale identity fields",
                )
            )
        normalized[slot] = column_name
    return normalized


def _compile_locale_selector(
    raw_bundle: dict[str, object],
    *,
    location: str,
) -> tuple[list[str], list[float]]:
    locale_raw = raw_bundle.get("locale")
    locale_weights_raw = raw_bundle.get("locale_weights")
    supported_locales = set(LOCALE_IDENTITY_PACKS.keys())

    if locale_raw is not None and locale_weights_raw is not None:
        raise ValueError(
            _runtime_error(
                location,
                "locale and locale_weights cannot both be set",
                "set exactly one of locale or locale_weights, or omit both to use default locale",
            )
        )
    if locale_raw is not None:
        if not isinstance(locale_raw, str) or locale_raw.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "locale must be a non-empty string when provided",
                    f"use one of: {', '.join(sorted(supported_locales))}",
                )
            )
        locale_name = locale_raw.strip()
        if locale_name not in supported_locales:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported locale '{locale_raw}'",
                    f"use one of: {', '.join(sorted(supported_locales))}",
                )
            )
        return [locale_name], [1.0]

    if locale_weights_raw is None:
        return ["en-US"], [1.0]

    if not isinstance(locale_weights_raw, dict) or len(locale_weights_raw) == 0:
        raise ValueError(
            _runtime_error(
                location,
                "locale_weights must be a non-empty object when provided",
                "set locale_weights to a mapping of locale ids to non-negative numeric weights",
            )
        )

    locales: list[str] = []
    weights: list[float] = []
    has_positive_weight = False
    for raw_locale, raw_weight in locale_weights_raw.items():
        if not isinstance(raw_locale, str) or raw_locale.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "locale_weights contains an empty or non-string locale key",
                    f"use supported locale ids as keys: {', '.join(sorted(supported_locales))}",
                )
            )
        locale_name = raw_locale.strip()
        if locale_name not in supported_locales:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported locale_weights key '{raw_locale}'",
                    f"use one of: {', '.join(sorted(supported_locales))}",
                )
            )
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"locale_weights['{raw_locale}'] must be numeric",
                    "use non-negative finite numeric weights",
                )
            ) from exc
        if (not math.isfinite(weight)) or weight < 0.0:
            raise ValueError(
                _runtime_error(
                    location,
                    f"locale_weights['{raw_locale}'] must be a finite value >= 0",
                    "use non-negative finite numeric weights",
                )
            )
        if weight > 0.0:
            has_positive_weight = True
        locales.append(locale_name)
        weights.append(weight)

    if not has_positive_weight:
        raise ValueError(
            _runtime_error(
                location,
                "locale_weights provides no positive weight",
                "set at least one locale weight > 0",
            )
        )
    return locales, weights


def _compile_locale_identity_bundles(project: SchemaProject) -> dict[str, dict[str, list[dict[str, object]]]]:
    raw_bundles = project.locale_identity_bundles
    if not raw_bundles:
        return {"base_by_table": {}, "related_by_table": {}}

    table_map = {table.table_name: table for table in project.tables}
    base_by_table: dict[str, list[dict[str, object]]] = {}
    related_by_table: dict[str, list[dict[str, object]]] = {}

    for bundle_index, raw_bundle in enumerate(raw_bundles):
        location = f"Project locale_identity_bundles[{bundle_index}]"
        if not isinstance(raw_bundle, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "bundle must be an object",
                    "set each locale_identity_bundles item to a JSON object",
                )
            )

        bundle_id_raw = raw_bundle.get("bundle_id")
        if not isinstance(bundle_id_raw, str) or bundle_id_raw.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "bundle_id is required",
                    "set bundle_id to a non-empty string",
                )
            )
        bundle_id = bundle_id_raw.strip()

        base_table_raw = raw_bundle.get("base_table")
        if not isinstance(base_table_raw, str) or base_table_raw.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "base_table is required",
                    "set base_table to an existing table name",
                )
            )
        base_table_name = base_table_raw.strip()
        base_table = table_map.get(base_table_name)
        if base_table is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"base_table '{base_table_name}' was not found",
                    "use an existing table name for base_table",
                )
            )
        base_columns = {column.name: column for column in base_table.columns}
        base_column_map = _normalize_locale_identity_columns(
            raw_bundle.get("columns"),
            location=location,
            table_name=base_table_name,
            table_columns=base_columns,
        )
        locale_ids, locale_weights = _compile_locale_selector(raw_bundle, location=location)

        base_by_table.setdefault(base_table_name, []).append(
            {
                "bundle_id": bundle_id,
                "bundle_index": bundle_index,
                "table": base_table_name,
                "pk_column": _table_pk_col_name(base_table),
                "columns": base_column_map,
                "locale_ids": locale_ids,
                "locale_weights": locale_weights,
            }
        )

        related_tables_raw = raw_bundle.get("related_tables")
        if related_tables_raw is None:
            continue
        if not isinstance(related_tables_raw, list):
            raise ValueError(
                _runtime_error(
                    location,
                    "related_tables must be a list when provided",
                    "set related_tables to a list of objects with table, via_fk, and columns",
                )
            )
        for related_index, raw_related in enumerate(related_tables_raw):
            related_location = f"{location}, related_tables[{related_index}]"
            if not isinstance(raw_related, dict):
                raise ValueError(
                    _runtime_error(
                        related_location,
                        "related table entry must be an object",
                        "configure table, via_fk, and columns for each related table object",
                    )
                )
            related_table_raw = raw_related.get("table")
            if not isinstance(related_table_raw, str) or related_table_raw.strip() == "":
                raise ValueError(
                    _runtime_error(
                        related_location,
                        "table is required",
                        "set table to an existing related table name",
                    )
                )
            related_table_name = related_table_raw.strip()
            related_table = table_map.get(related_table_name)
            if related_table is None:
                raise ValueError(
                    _runtime_error(
                        related_location,
                        f"table '{related_table_name}' was not found",
                        "use an existing related table name",
                    )
                )
            related_columns = {column.name: column for column in related_table.columns}

            via_fk_raw = raw_related.get("via_fk")
            if not isinstance(via_fk_raw, str) or via_fk_raw.strip() == "":
                raise ValueError(
                    _runtime_error(
                        related_location,
                        "via_fk is required",
                        "set via_fk to the related-table FK child column that references base_table",
                    )
                )
            via_fk = via_fk_raw.strip()
            if via_fk not in related_columns:
                raise ValueError(
                    _runtime_error(
                        related_location,
                        f"via_fk '{via_fk}' was not found on table '{related_table_name}'",
                        "use an existing related-table column for via_fk",
                    )
                )

            direct_fk = next(
                (
                    fk
                    for fk in project.foreign_keys
                    if fk.child_table == related_table_name
                    and fk.child_column == via_fk
                    and fk.parent_table == base_table_name
                ),
                None,
            )
            if direct_fk is None:
                raise ValueError(
                    _runtime_error(
                        related_location,
                        (
                            f"via_fk '{related_table_name}.{via_fk}' does not directly reference "
                            f"base_table '{base_table_name}'"
                        ),
                        "define a direct FK from related table via_fk to base_table before using this DG09 mapping",
                    )
                )

            related_column_map = _normalize_locale_identity_columns(
                raw_related.get("columns"),
                location=related_location,
                table_name=related_table_name,
                table_columns=related_columns,
            )
            related_by_table.setdefault(related_table_name, []).append(
                {
                    "bundle_id": bundle_id,
                    "bundle_index": bundle_index,
                    "related_index": related_index,
                    "base_table": base_table_name,
                    "table": related_table_name,
                    "via_fk": via_fk,
                    "columns": related_column_map,
                }
            )

    return {"base_by_table": base_by_table, "related_by_table": related_by_table}


def _format_locale_phone(
    *,
    locale_id: str,
    city_profile: dict[str, object],
    rng: random.Random,
) -> tuple[str, str]:
    raw_area_codes = city_profile.get("area_codes")
    area_codes = (
        [str(value).strip() for value in raw_area_codes if str(value).strip() != ""]
        if isinstance(raw_area_codes, list)
        else []
    )

    if locale_id == "en-US":
        area = rng.choice(area_codes) if area_codes else str(rng.randint(201, 989))
        prefix = rng.randint(200, 999)
        line = rng.randint(1000, 9999)
        national = f"({area}) {prefix:03d}-{line:04d}"
        e164 = f"+1{area}{prefix:03d}{line:04d}"
        return national, e164

    if locale_id == "en-GB":
        area = rng.choice(area_codes) if area_codes else "20"
        part_a = rng.randint(1000, 9999)
        part_b = rng.randint(1000, 9999)
        national = f"0{area} {part_a:04d} {part_b:04d}"
        e164 = f"+44{area}{part_a:04d}{part_b:04d}"
        return national, e164

    if locale_id == "fr-FR":
        area = rng.choice(area_codes) if area_codes else "1"
        groups = [rng.randint(0, 99) for _ in range(4)]
        tail = "".join(f"{group:02d}" for group in groups)
        national = f"0{area} " + " ".join(f"{group:02d}" for group in groups)
        e164 = f"+33{area}{tail}"
        return national, e164

    area = rng.choice(area_codes) if area_codes else "30"
    part_a = rng.randint(100, 999)
    part_b = rng.randint(1000, 9999)
    national = f"0{area} {part_a:03d} {part_b:04d}"
    e164 = f"+49{area}{part_a:03d}{part_b:04d}"
    return national, e164


def _build_locale_identity_payload(
    *,
    locale_id: str,
    rng: random.Random,
) -> dict[str, object]:
    pack = LOCALE_IDENTITY_PACKS.get(locale_id)
    if pack is None:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"unsupported locale '{locale_id}'",
                f"use one of: {', '.join(sorted(LOCALE_IDENTITY_PACKS.keys()))}",
            )
        )

    first_names_raw = pack.get("first_names")
    last_names_raw = pack.get("last_names")
    streets_raw = pack.get("streets")
    cities_raw = pack.get("cities")
    if not isinstance(first_names_raw, list) or not first_names_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no first_names",
                "provide one or more first_names in the locale pack",
            )
        )
    if not isinstance(last_names_raw, list) or not last_names_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no last_names",
                "provide one or more last_names in the locale pack",
            )
        )
    if not isinstance(streets_raw, list) or not streets_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no streets",
                "provide one or more streets in the locale pack",
            )
        )
    if not isinstance(cities_raw, list) or not cities_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no cities",
                "provide one or more city profiles in the locale pack",
            )
        )

    first_name = str(rng.choice(first_names_raw))
    last_name = str(rng.choice(last_names_raw))
    street = str(rng.choice(streets_raw))
    city_profile_raw = rng.choice(cities_raw)
    if not isinstance(city_profile_raw, dict):
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' city profile must be an object",
                "fix locale pack city entries so each value is an object",
            )
        )
    city_profile = city_profile_raw

    city_name = str(city_profile.get("city", "")).strip()
    region = str(city_profile.get("region", "")).strip()
    if city_name == "" or region == "":
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' city profile requires city and region",
                "set city and region for each locale city profile",
            )
        )

    postcodes_raw = city_profile.get("postcodes")
    if not isinstance(postcodes_raw, list) or not postcodes_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' city profile has no postcodes",
                "set one or more postcode values in each city profile",
            )
        )
    postcode = str(rng.choice(postcodes_raw)).strip()
    if postcode == "":
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' produced an empty postcode value",
                "use non-empty postcode values in locale packs",
            )
        )

    national_phone, phone_e164 = _format_locale_phone(locale_id=locale_id, city_profile=city_profile, rng=rng)
    house_number = rng.randint(1, 9999)
    full_name = f"{first_name} {last_name}"
    return {
        "locale": locale_id,
        "country_code": str(pack.get("country_code", "")).strip(),
        "currency_code": str(pack.get("currency_code", "")).strip(),
        "currency_symbol": str(pack.get("currency_symbol", "")).strip(),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "address_line1": f"{house_number} {street}",
        "city": city_name,
        "region": region,
        "postcode": postcode,
        "phone_e164": phone_e164,
        "phone_national": national_phone,
    }


def _apply_table_locale_identity_bundles(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    project_seed: int,
    compiled_bundles: dict[str, dict[str, list[dict[str, object]]]],
    bundle_state: dict[str, dict[tuple[str, object], dict[str, object]]],
) -> None:
    if not rows:
        return
    base_by_table = compiled_bundles.get("base_by_table")
    related_by_table = compiled_bundles.get("related_by_table")
    if not isinstance(base_by_table, dict) or not isinstance(related_by_table, dict):
        return

    base_specs = base_by_table.get(table.table_name, [])
    for spec in base_specs:
        bundle_id = str(spec.get("bundle_id", "")).strip()
        bundle_index = int(spec.get("bundle_index", 0))
        pk_column = str(spec.get("pk_column", "")).strip()
        column_map = spec.get("columns")
        locale_ids_raw = spec.get("locale_ids")
        locale_weights_raw = spec.get("locale_weights")
        if bundle_id == "" or pk_column == "":
            continue
        if not isinstance(column_map, dict):
            continue
        if not isinstance(locale_ids_raw, list) or not locale_ids_raw:
            continue
        if not isinstance(locale_weights_raw, list) or len(locale_weights_raw) != len(locale_ids_raw):
            continue
        locale_ids = [str(locale).strip() for locale in locale_ids_raw if str(locale).strip() != ""]
        if not locale_ids:
            continue
        locale_weights = [float(weight) for weight in locale_weights_raw]

        bundle_rng = random.Random(
            _stable_subseed(project_seed, f"dg09:{table.table_name}:{bundle_id}:{bundle_index}")
        )
        values_by_key = bundle_state.setdefault(bundle_id, {})

        for row_index, row in enumerate(rows, start=1):
            key = _fk_lookup_identity(row.get(pk_column))
            if key[0] == "none":
                raise ValueError(
                    _runtime_error(
                        f"Table '{table.table_name}', row {row_index}, column '{pk_column}'",
                        "DG09 base key resolved to null",
                        "ensure the base table primary key column is populated before locale bundle application",
                    )
                )

            payload = values_by_key.get(key)
            if payload is None:
                locale_id = str(bundle_rng.choices(locale_ids, weights=locale_weights, k=1)[0])
                payload = _build_locale_identity_payload(locale_id=locale_id, rng=bundle_rng)
                values_by_key[key] = payload

            for slot, column_name_raw in column_map.items():
                column_name = str(column_name_raw).strip()
                if column_name == "":
                    continue
                row[column_name] = payload.get(slot)

    related_specs = related_by_table.get(table.table_name, [])
    for spec in related_specs:
        bundle_id = str(spec.get("bundle_id", "")).strip()
        via_fk = str(spec.get("via_fk", "")).strip()
        column_map = spec.get("columns")
        if bundle_id == "" or via_fk == "":
            continue
        if not isinstance(column_map, dict):
            continue
        values_by_key = bundle_state.get(bundle_id)
        if not values_by_key:
            raise ValueError(
                _runtime_error(
                    f"Table '{table.table_name}'",
                    f"DG09 bundle '{bundle_id}' has no resolved base-table payloads",
                    "generate base table rows before related-table DG09 projections",
                )
            )
        for row_index, row in enumerate(rows, start=1):
            key = _fk_lookup_identity(row.get(via_fk))
            if key[0] == "none":
                continue
            payload = values_by_key.get(key)
            if payload is None:
                raise ValueError(
                    _runtime_error(
                        f"Table '{table.table_name}', row {row_index}, FK column '{via_fk}'",
                        f"DG09 could not find a base bundle payload for value {row.get(via_fk)!r}",
                        "ensure via_fk references an existing base-table key populated by the DG09 bundle",
                    )
                )
            for slot, column_name_raw in column_map.items():
                column_name = str(column_name_raw).strip()
                if column_name == "":
                    continue
                row[column_name] = payload.get(slot)


def _read_csv_profile_source(
    *,
    location: str,
    source: dict[str, object],
) -> tuple[str, int, list[str]]:
    path_raw = source.get("path")
    if not isinstance(path_raw, str) or path_raw.strip() == "":
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.path is required",
                "set sample_source.path to an existing CSV file path",
            )
        )
    raw_path = path_raw.strip()
    resolved_path = resolve_repo_path(raw_path)
    if not resolved_path.exists():
        raise ValueError(
            _runtime_error(
                location,
                f"sample_source.path '{raw_path}' does not exist",
                "provide an existing CSV file path",
            )
        )

    has_header_raw = source.get("has_header", True)
    if not isinstance(has_header_raw, bool):
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.has_header must be boolean when provided",
                "set sample_source.has_header to true or false",
            )
        )
    has_header = bool(has_header_raw)

    has_index = "column_index" in source
    has_name = "column_name" in source
    if has_index == has_name:
        raise ValueError(
            _runtime_error(
                location,
                "sample_source requires exactly one of column_index or column_name",
                "set either sample_source.column_index or sample_source.column_name",
            )
        )

    skip_empty_raw = source.get("skip_empty", True)
    if not isinstance(skip_empty_raw, bool):
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.skip_empty must be boolean when provided",
                "set sample_source.skip_empty to true or false",
            )
        )
    skip_empty = bool(skip_empty_raw)

    rows: list[list[str]] = []
    with resolved_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(list(row))
    if not rows:
        raise ValueError(
            _runtime_error(
                location,
                f"sample CSV '{raw_path}' has no rows",
                "provide a CSV file with header/data rows for DG07 fitting",
            )
        )

    data_rows = rows
    resolved_index: int
    if has_header:
        header = rows[0]
        data_rows = rows[1:]
        if has_name:
            column_name_raw = source.get("column_name")
            column_name = str(column_name_raw).strip()
            if column_name not in header:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample_source.column_name '{column_name}' was not found in CSV header",
                        "use an existing CSV header name or switch to column_index",
                    )
                )
            resolved_index = header.index(column_name)
        else:
            try:
                resolved_index = int(source.get("column_index"))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        "sample_source.column_index must be an integer",
                        "set sample_source.column_index to 0 or greater",
                    )
                ) from exc
    else:
        if has_name:
            raise ValueError(
                _runtime_error(
                    location,
                    "sample_source.column_name requires sample_source.has_header=true",
                    "set has_header=true when using column_name or use column_index",
                )
            )
        try:
            resolved_index = int(source.get("column_index"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    "sample_source.column_index must be an integer",
                    "set sample_source.column_index to 0 or greater",
                )
            ) from exc

    if resolved_index < 0:
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.column_index cannot be negative",
                "set sample_source.column_index to 0 or greater",
            )
        )

    values: list[str] = []
    for row in data_rows:
        if resolved_index >= len(row):
            continue
        cell = row[resolved_index]
        if skip_empty and cell.strip() == "":
            continue
        values.append(cell)
    if not values:
        raise ValueError(
            _runtime_error(
                location,
                "sample_source produced zero eligible values",
                "point to a populated CSV column or disable skip_empty",
            )
        )

    normalized_path = to_repo_relative_path(raw_path)
    return normalized_path, resolved_index, values


def _infer_profile_from_values(
    *,
    location: str,
    dtype: str,
    source_path: str,
    source_column_index: int,
    values: list[str],
) -> tuple[str, dict[str, object]]:
    if dtype == "int":
        parsed: list[int] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                parsed.append(int(text))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not integer-like",
                        "clean sample values or use fixed_profile for non-integer source data",
                    )
                ) from exc
        return "uniform_int", {"min": min(parsed), "max": max(parsed)}

    if dtype in {"float", "decimal"}:
        parsed_numeric: list[float] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                parsed_numeric.append(float(text))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not numeric",
                        "clean sample values or use fixed_profile for non-numeric source data",
                    )
                ) from exc
        min_value = min(parsed_numeric)
        max_value = max(parsed_numeric)
        if min_value == max_value:
            return "uniform_float", {"min": min_value, "max": max_value}
        mean_value = sum(parsed_numeric) / len(parsed_numeric)
        variance = sum((value - mean_value) ** 2 for value in parsed_numeric) / len(parsed_numeric)
        stdev = variance ** 0.5
        if stdev <= 0.0:
            stdev = (max_value - min_value) / 6.0
        if stdev <= 0.0:
            stdev = 1.0
        return "normal", {"mean": mean_value, "stdev": stdev, "min": min_value, "max": max_value}

    if dtype == "text":
        counts: dict[str, int] = {}
        order: list[str] = []
        for value in values:
            if value not in counts:
                counts[value] = 0
                order.append(value)
            counts[value] += 1
        choices = order
        weights = [float(counts[value]) for value in choices]
        return "choice_weighted", {"choices": choices, "weights": weights}

    if dtype == "date":
        parsed_dates: list[date] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                parsed_dates.append(date.fromisoformat(text))
            except Exception as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not a valid ISO date",
                        "clean sample values to 'YYYY-MM-DD' or use fixed_profile",
                    )
                ) from exc
        return "date", {"start": min(parsed_dates).isoformat(), "end": max(parsed_dates).isoformat()}

    if dtype == "datetime":
        parsed_datetimes: list[datetime] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not a valid ISO datetime",
                        "clean sample values to ISO datetime text or use fixed_profile",
                    )
                ) from exc
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            parsed_datetimes.append(dt)
        return "timestamp_utc", {
            "start": _iso_datetime(min(parsed_datetimes)),
            "end": _iso_datetime(max(parsed_datetimes)),
        }

    raise ValueError(
        _runtime_error(
            location,
            f"sample_source inference does not support dtype '{dtype}'",
            "use fixed_profile for this target dtype",
        )
    )


def _resolve_sample_profile_fits(project: SchemaProject) -> SchemaProject:
    fit_specs = project.sample_profile_fits
    if not fit_specs:
        return project

    table_map = {table.table_name: table for table in project.tables}
    overrides: dict[tuple[str, str], tuple[str, dict[str, object], list[str] | None]] = {}

    for fit_index, raw_fit in enumerate(fit_specs):
        location = f"Project sample_profile_fits[{fit_index}]"
        if not isinstance(raw_fit, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "fit must be an object",
                    "set each sample_profile_fits item to a JSON object",
                )
            )

        table_name = str(raw_fit.get("table", "")).strip()
        column_name = str(raw_fit.get("column", "")).strip()
        table = table_map.get(table_name)
        if table is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"table '{table_name}' was not found",
                    "use an existing table name for DG07 profile fits",
                )
            )
        column = next((candidate for candidate in table.columns if candidate.name == column_name), None)
        if column is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"column '{column_name}' was not found on table '{table_name}'",
                    "use an existing target column for DG07 profile fits",
                )
            )

        fixed_profile_raw = raw_fit.get("fixed_profile")
        if isinstance(fixed_profile_raw, dict):
            generator_raw = fixed_profile_raw.get("generator")
            if not isinstance(generator_raw, str) or generator_raw.strip() == "":
                raise ValueError(
                    _runtime_error(
                        location,
                        "fixed_profile.generator is required",
                        "set fixed_profile.generator to a registered generator id",
                    )
                )
            generator = generator_raw.strip()
            try:
                get_generator(generator)
            except KeyError as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"fixed_profile.generator '{generator}' is not registered",
                        "set fixed_profile.generator to a registered generator id",
                    )
                ) from exc
            params_raw = fixed_profile_raw.get("params", {})
            if not isinstance(params_raw, dict):
                raise ValueError(
                    _runtime_error(
                        location,
                        "fixed_profile.params must be an object when provided",
                        "set fixed_profile.params to a JSON object",
                    )
                )
            depends_on_raw = fixed_profile_raw.get("depends_on")
            depends_on: list[str] | None = None
            if isinstance(depends_on_raw, list):
                depends_on = [str(name).strip() for name in depends_on_raw if str(name).strip() != ""]
            overrides[(table_name, column_name)] = (generator, dict(params_raw), depends_on)
            continue

        sample_source_raw = raw_fit.get("sample_source")
        if not isinstance(sample_source_raw, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "requires fixed_profile or sample_source",
                    "set fixed_profile for frozen deterministic profiles or sample_source for CSV-driven inference",
                )
            )
        source_path, source_column_index, values = _read_csv_profile_source(
            location=location,
            source=sample_source_raw,
        )
        generator, params = _infer_profile_from_values(
            location=location,
            dtype=column.dtype,
            source_path=source_path,
            source_column_index=source_column_index,
            values=values,
        )
        if generator == "sample_csv":
            params["path"] = source_path
            params["column_index"] = source_column_index
        overrides[(table_name, column_name)] = (generator, params, None)

    new_tables: list[TableSpec] = []
    for table in project.tables:
        new_columns: list[ColumnSpec] = []
        for column in table.columns:
            key = (table.table_name, column.name)
            override = overrides.get(key)
            if override is None:
                new_columns.append(column)
                continue
            generator, params, depends_on = override
            updated = ColumnSpec(
                name=column.name,
                dtype=column.dtype,
                nullable=column.nullable,
                primary_key=column.primary_key,
                unique=column.unique,
                min_value=column.min_value,
                max_value=column.max_value,
                choices=column.choices,
                pattern=column.pattern,
                generator=generator,
                params=params,
                depends_on=(depends_on if depends_on is not None else column.depends_on),
            )
            new_columns.append(updated)
        new_tables.append(
            TableSpec(
                table_name=table.table_name,
                columns=new_columns,
                row_count=table.row_count,
                business_key=table.business_key,
                business_key_unique_count=table.business_key_unique_count,
                business_key_static_columns=table.business_key_static_columns,
                business_key_changing_columns=table.business_key_changing_columns,
                scd_mode=table.scd_mode,
                scd_tracked_columns=table.scd_tracked_columns,
                scd_active_from_column=table.scd_active_from_column,
                scd_active_to_column=table.scd_active_to_column,
                correlation_groups=table.correlation_groups,
            )
        )

    return SchemaProject(
        name=project.name,
        seed=project.seed,
        tables=new_tables,
        foreign_keys=project.foreign_keys,
        timeline_constraints=project.timeline_constraints,
        data_quality_profiles=project.data_quality_profiles,
        sample_profile_fits=project.sample_profile_fits,
        locale_identity_bundles=project.locale_identity_bundles,
    )

def _maybe_null(col, ctx: GenContext) -> bool:
    # PKs cannot be null
    if getattr(col, "primary_key", False):
        return False

    params = getattr(col, "params", None) or {}
    null_rate = params.get("null_rate", None)
    if null_rate is None:
        return False

    r = float(null_rate)
    if r <= 0.0:
        return False
    if r >= 1.0:
        return True
    return ctx.rng.random() < r


def _apply_numeric_post(col, v: object) -> object:
    if v is None:
        return None
    if not isinstance(v, (int, float)):
        return v

    params = getattr(col, "params", None) or {}
    mn = params.get("clamp_min", None)
    mx = params.get("clamp_max", None)

    x = float(v)
    if mn is not None:
        x = max(float(mn), x)
    if mx is not None:
        x = min(float(mx), x)

    # If dtype says int, keep int
    if getattr(col, "dtype", "") == "int":
        return int(round(x))

    if getattr(col, "dtype", "") == "decimal":
        scale = params.get("scale", None)
        if scale is not None:
            x = round(x, int(scale))
        return float(x)

    return x


def _categorical_order_lookup(order_values: object) -> dict[object, int]:
    if not isinstance(order_values, list):
        return {}
    lookup: dict[object, int] = {}
    for idx, value in enumerate(order_values):
        if value not in lookup:
            lookup[value] = idx
        text_key = str(value)
        if text_key not in lookup:
            lookup[text_key] = idx
    return lookup


def _correlation_sort_key(value: object, *, categorical_order: dict[object, int]) -> tuple[int, float, str]:
    if value is None:
        return (0, 0.0, "")

    try:
        if value in categorical_order:
            return (1, float(categorical_order[value]), "")
    except TypeError:
        pass
    text_value = str(value)
    if text_value in categorical_order:
        return (1, float(categorical_order[text_value]), "")

    if isinstance(value, bool):
        return (2, 1.0 if value else 0.0, "")
    if isinstance(value, (int, float)):
        return (2, float(value), "")
    return (3, 0.0, text_value)


def _apply_table_correlation_groups(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    project_seed: int,
) -> None:
    groups = table.correlation_groups
    if not rows or not groups:
        return
    if not isinstance(groups, list):
        return

    for group_index, raw_group in enumerate(groups):
        if not isinstance(raw_group, dict):
            continue
        columns_raw = raw_group.get("columns")
        matrix_raw = raw_group.get("rank_correlation")
        if not isinstance(columns_raw, list) or not isinstance(matrix_raw, list):
            continue
        columns = [name.strip() for name in columns_raw if isinstance(name, str) and name.strip() != ""]
        if len(columns) < 2:
            continue
        size = len(columns)
        if len(matrix_raw) != size:
            continue

        matrix: list[list[float]] = []
        matrix_valid = True
        for row_raw in matrix_raw:
            if not isinstance(row_raw, list) or len(row_raw) != size:
                matrix_valid = False
                break
            try:
                matrix.append([float(value) for value in row_raw])
            except (TypeError, ValueError):
                matrix_valid = False
                break
        if not matrix_valid:
            continue

        try:
            lower = correlation_cholesky_lower(matrix)
        except ValueError:
            continue

        try:
            strength = float(raw_group.get("strength", 1.0))
        except (TypeError, ValueError):
            strength = 1.0
        if strength <= 0.0:
            continue
        if strength > 1.0:
            strength = 1.0

        categorical_orders_raw = raw_group.get("categorical_orders")
        categorical_orders: dict[str, dict[object, int]] = {}
        if isinstance(categorical_orders_raw, dict):
            for key, value in categorical_orders_raw.items():
                if isinstance(key, str):
                    categorical_orders[key.strip()] = _categorical_order_lookup(value)

        eligible_indices = [
            idx
            for idx, row in enumerate(rows)
            if all(row.get(column_name) is not None for column_name in columns)
        ]
        if len(eligible_indices) < 2:
            continue

        sorted_values_by_column: dict[str, list[object]] = {}
        for column_name in columns:
            order_lookup = categorical_orders.get(column_name, {})
            ordered_row_indices = sorted(
                eligible_indices,
                key=lambda row_idx: (
                    _correlation_sort_key(rows[row_idx].get(column_name), categorical_order=order_lookup),
                    row_idx,
                ),
            )
            sorted_values_by_column[column_name] = [rows[row_idx].get(column_name) for row_idx in ordered_row_indices]

        group_id_raw = raw_group.get("group_id")
        if isinstance(group_id_raw, str) and group_id_raw.strip() != "":
            group_id = group_id_raw.strip()
        else:
            group_id = f"group_{group_index + 1}"
        group_rng = random.Random(_stable_subseed(project_seed, f"corr:{table.table_name}:{group_id}"))

        eligible_count = len(eligible_indices)
        scores: list[list[float]] = [[0.0 for _ in range(size)] for _ in range(eligible_count)]
        for local_idx in range(eligible_count):
            base_draw = [group_rng.gauss(0.0, 1.0) for _ in range(size)]
            correlated = [0.0 for _ in range(size)]
            for row_idx in range(size):
                total = 0.0
                for col_idx in range(row_idx + 1):
                    total += lower[row_idx][col_idx] * base_draw[col_idx]
                correlated[row_idx] = total
            if strength < 1.0:
                noise = [group_rng.gauss(0.0, 1.0) for _ in range(size)]
                for score_idx in range(size):
                    correlated[score_idx] = (strength * correlated[score_idx]) + (
                        (1.0 - strength) * noise[score_idx]
                    )
            scores[local_idx] = correlated

        for col_idx, column_name in enumerate(columns):
            ranked_local_indices = sorted(
                range(eligible_count),
                key=lambda local_idx: (scores[local_idx][col_idx], local_idx),
            )
            sorted_values = sorted_values_by_column.get(column_name, [])
            if len(sorted_values) != eligible_count:
                continue
            for rank_idx, local_idx in enumerate(ranked_local_indices):
                row_idx = eligible_indices[local_idx]
                rows[row_idx][column_name] = sorted_values[rank_idx]


def _gen_value(col: ColumnSpec, rng: random.Random, row_index: int, table_name: str, row: dict[str, object]) -> object:
    ctx = GenContext(
        row_index=row_index,
        table=table_name,
        row=row,
        rng=rng,
        column=col.name,
        dtype=col.dtype,
    )

    # Nulls (probabilistic)
    if _maybe_null(col, ctx):
        return None

    # Generate
    if getattr(col, "generator", None):
        try:
            fn = get_generator(col.generator)  # type: ignore[arg-type]
        except KeyError as exc:
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}', column '{col.name}'",
                    f"unknown generator '{col.generator}'",
                    "choose a registered generator name in column.generator",
                )
            ) from exc
        params = col.params or {}
        try:
            v = fn(params, ctx)
        except KeyError as exc:
            missing = str(exc.args[0]) if exc.args else "unknown"
            raise ValueError(
                f"Table '{table_name}', column '{col.name}': generator '{col.generator}' is missing required params key '{missing}'. "
                "Fix: set the required key in params before generation."
            ) from exc

        # Optional numeric outliers (only when numeric)
        out_rate = float(params.get("outlier_rate", 0.0) or 0.0)
        out_scale = float(params.get("outlier_scale", 3.0) or 3.0)
        if out_rate > 0 and isinstance(v, (int, float)) and rng.random() < out_rate:
            v = float(v) * out_scale

    else:
        v = _gen_value_fallback(col, rng, row_index)

    # Post-processing
    v = _apply_numeric_post(col, v)

    # choices override (if set)
    if col.choices:
        v = rng.choice(col.choices)

    # regex validation (if set)
    if col.pattern and v is not None:
        import re
        if not re.fullmatch(col.pattern, str(v)):
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}', column '{col.name}'",
                    f"value '{v}' does not match pattern '{col.pattern}'",
                    "adjust the generator output or update the regex pattern",
                )
            )

    return v





def _gen_value_fallback(col: ColumnSpec, rng: random.Random, row_index: int) -> object:
    # Null handling
    if col.nullable and rng.random() < 0.05:  # 5% nulls
        return None

    # Primary key: deterministic increasing integer (1..N)
    if col.primary_key:
        return row_index

    # Choices override
    if col.choices is not None:
        return rng.choice(col.choices)

    if col.dtype == "int":
        lo = int(col.min_value) if col.min_value is not None else 0
        hi = int(col.max_value) if col.max_value is not None else 1000
        return rng.randint(lo, hi)

    if col.dtype in {"float", "decimal"}:
        lo = float(col.min_value) if col.min_value is not None else 0.0
        hi = float(col.max_value) if col.max_value is not None else 1000.0
        return round(rng.uniform(lo, hi), 2)

    if col.dtype == "bool":
        return 1 if rng.random() < 0.5 else 0

    if col.dtype == "date":
        base = date(2020, 1, 1)
        d = base + timedelta(days=rng.randint(0, 3650))
        return _iso_date(d)

    if col.dtype == "datetime":
        base = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=rng.randint(0, 10_000_000))
        dt = base - timedelta(seconds=rng.randint(0, 3600 * 24 * 30))
        return _iso_datetime(dt)

    if col.dtype == "text":
        pattern = re.compile(col.pattern) if col.pattern else None
        letters = "abcdefghijklmnopqrstuvwxyz"

        def candidate() -> str:
            length = rng.randint(5, 14)
            return "".join(rng.choice(letters) for _ in range(length))

        for _ in range(50):
            s = candidate()
            if pattern is None or pattern.fullmatch(s):
                return s
        return candidate()

    if col.dtype == "bytes":
        params = col.params if isinstance(col.params, dict) else {}
        try:
            min_len = int(params.get("min_length", 8))
        except (TypeError, ValueError):
            min_len = 8
        try:
            max_len = int(params.get("max_length", min_len))
        except (TypeError, ValueError):
            max_len = min_len
        min_len = max(0, min_len)
        max_len = max(min_len, max_len)
        size = rng.randint(min_len, max_len)
        return bytes(rng.getrandbits(8) for _ in range(size))

    raise ValueError(
        _runtime_error(
            f"Column '{col.name}'",
            f"unsupported dtype '{col.dtype}' during runtime fallback generation",
            "use a supported dtype or configure a compatible generator",
        )
    )


def _dependency_order(project: SchemaProject) -> list[str]:
    """
    Return table names in parent->child order using Kahn's algorithm.
    MVP guarantees <=1 FK per child, but algorithm works regardless.
    """
    table_names = [t.table_name for t in project.tables]
    deps = {t: set() for t in table_names}       # t depends on these
    rev = {t: set() for t in table_names}        # these depend on t

    for fk in project.foreign_keys:
        child = fk.child_table
        parent = fk.parent_table
        deps[child].add(parent)
        rev[parent].add(child)

    # Optional additional fk sort
    # fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    # for fk in project.foreign_keys:
    #     fks_by_child.setdefault(fk.child_table, []).append(fk)

    # Kahn
    ready = [t for t in table_names if len(deps[t]) == 0]
    ready.sort()
    out = []

    while ready:
        n = ready.pop(0)
        out.append(n)
        for child in sorted(rev[n]):
            deps[child].discard(n)
            if len(deps[child]) == 0:
                ready.append(child)
                ready.sort()

    if len(out) != len(table_names):
        raise ValueError(
            _runtime_error(
                "Project foreign keys",
                "cycle detected in table dependency graph",
                "remove circular foreign key dependencies",
            )
        )

    return out


def _table_pk_col_name(table: TableSpec) -> str:
    return [c.name for c in table.columns if c.primary_key][0]


def _table_col_map(table: TableSpec) -> dict[str, ColumnSpec]:
    return {c.name: c for c in table.columns}


def _normalize_scd_mode(table: TableSpec) -> str | None:
    if not isinstance(table.scd_mode, str):
        return None
    mode = table.scd_mode.strip().lower()
    return mode or None


def _effective_scd_tracked_columns(table: TableSpec) -> list[str]:
    return list(table.business_key_changing_columns or table.scd_tracked_columns or [])


def _business_key_is_already_unique(rows: list[dict[str, object]], key_cols: list[str]) -> bool:
    if not rows:
        return True
    tuples = [tuple(r.get(k) for k in key_cols) for r in rows]
    if any(any(v is None for v in t) for t in tuples):
        return False
    return len(set(tuples)) == len(tuples)


def _business_key_value_for_row(col: ColumnSpec, *, table_name: str, row_num: int) -> object:
    if col.dtype == "int":
        return row_num
    if col.dtype in {"float", "decimal"}:
        return float(row_num)
    if col.dtype == "text":
        return f"{table_name}_{col.name}_{row_num}"
    if col.dtype == "date":
        return _iso_date(date(2020, 1, 1) + timedelta(days=row_num))
    if col.dtype == "datetime":
        return _iso_datetime(datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=row_num))
    raise ValueError(
        f"Table '{table_name}', column '{col.name}': unsupported business key dtype '{col.dtype}'. "
        "Fix: use int/text/decimal/date/datetime business_key columns."
    )


def _enforce_business_key_uniqueness(table: TableSpec, rows: list[dict[str, object]]) -> None:
    key_cols = list(table.business_key or [])
    if not key_cols or not rows:
        return
    if _business_key_is_already_unique(rows, key_cols):
        return

    col_map = _table_col_map(table)
    for row_num, row in enumerate(rows, start=1):
        for key_col in key_cols:
            row[key_col] = _business_key_value_for_row(
                col_map[key_col],
                table_name=table.table_name,
                row_num=row_num,
            )


def _parse_business_key_unique_count(table: TableSpec, *, row_total: int) -> int | None:
    raw_count = table.business_key_unique_count
    if raw_count is None:
        return None
    if isinstance(raw_count, bool):
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count must be an integer when provided. "
            "Fix: set business_key_unique_count to a positive whole number."
        )
    try:
        count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count must be an integer when provided. "
            "Fix: set business_key_unique_count to a positive whole number."
        ) from exc

    if count <= 0:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count must be > 0. "
            "Fix: set business_key_unique_count to a positive whole number."
        )
    if count > row_total:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count={count} cannot exceed generated row count={row_total}. "
            "Fix: reduce business_key_unique_count or increase table row_count."
        )
    return count


def _enforce_business_key_unique_count(table: TableSpec, rows: list[dict[str, object]]) -> None:
    key_cols = list(table.business_key or [])
    target_unique = _parse_business_key_unique_count(table, row_total=len(rows))
    if target_unique is None or not rows:
        return
    if not key_cols:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count requires business_key. "
            "Fix: configure business_key columns before setting business_key_unique_count."
        )

    col_map = _table_col_map(table)
    key_values: list[tuple[object, ...]] = []
    for key_idx in range(1, target_unique + 1):
        key_values.append(
            tuple(
                _business_key_value_for_row(
                    col_map[key_col],
                    table_name=table.table_name,
                    row_num=key_idx,
                )
                for key_col in key_cols
            )
        )

    for row_idx, row in enumerate(rows):
        values = key_values[row_idx % target_unique]
        for key_col, value in zip(key_cols, values, strict=True):
            row[key_col] = value


def _mutate_scd_tracked_value(
    col: ColumnSpec,
    value: object,
    *,
    version_idx: int,
    rng: random.Random,
) -> object:
    if col.generator == "ordered_choice":
        params = col.params if isinstance(col.params, dict) else {}
        orders_raw = params.get("orders")
        if isinstance(orders_raw, dict) and orders_raw:
            sequences: list[list[object]] = [
                seq for seq in orders_raw.values() if isinstance(seq, list) and len(seq) > 0
            ]
            if sequences:
                seq_match: list[object] | None = None
                idx_match: int | None = None

                for seq in sequences:
                    for idx, item in enumerate(seq):
                        if item == value:
                            seq_match = seq
                            idx_match = idx
                            break
                    if seq_match is not None:
                        break

                if seq_match is None:
                    value_text = str(value)
                    for seq in sequences:
                        for idx, item in enumerate(seq):
                            if str(item) == value_text:
                                seq_match = seq
                                idx_match = idx
                                break
                        if seq_match is not None:
                            break

                if seq_match is None:
                    seq_match = sequences[0]
                    start_raw = params.get("start_index", 0)
                    try:
                        start_idx = int(start_raw)
                    except (TypeError, ValueError):
                        start_idx = 0
                    idx_match = max(0, min(start_idx, len(seq_match) - 1))

                move_weights = [0.0, 1.0]
                move_weights_raw = params.get("move_weights")
                if isinstance(move_weights_raw, list) and len(move_weights_raw) > 0:
                    parsed_weights: list[float] = []
                    for raw in move_weights_raw:
                        try:
                            weight = float(raw)
                        except (TypeError, ValueError):
                            parsed_weights = []
                            break
                        if weight < 0:
                            parsed_weights = []
                            break
                        parsed_weights.append(weight)
                    if parsed_weights and any(weight > 0 for weight in parsed_weights):
                        move_weights = parsed_weights

                out_idx = int(idx_match)
                steps = max(1, version_idx)
                for _ in range(steps):
                    step = rng.choices(range(len(move_weights)), weights=move_weights, k=1)[0]
                    out_idx = min(out_idx + int(step), len(seq_match) - 1)
                return seq_match[out_idx]

    if col.generator == "state_transition":
        params = col.params if isinstance(col.params, dict) else {}
        states_raw = params.get("states")
        transitions_raw = params.get("transitions")
        if not isinstance(states_raw, list) or len(states_raw) == 0:
            return value
        if not isinstance(transitions_raw, dict) or len(transitions_raw) == 0:
            return value

        state_kind: str | None = None
        states: list[object] = []
        for raw_state in states_raw:
            if isinstance(raw_state, bool) or isinstance(raw_state, (dict, list)):
                return value
            if isinstance(raw_state, int):
                kind = "int"
                normalized_state: object = int(raw_state)
            elif isinstance(raw_state, str):
                if raw_state.strip() == "":
                    return value
                kind = "text"
                normalized_state = raw_state
            else:
                return value
            if state_kind is None:
                state_kind = kind
            elif state_kind != kind:
                return value
            states.append(normalized_state)
        if state_kind is None:
            return value

        state_set = set(states)

        def _coerce_state(
            raw_state: object,
            *,
            allow_int_string: bool,
        ) -> object | None:
            if state_kind == "int":
                if isinstance(raw_state, bool):
                    return None
                if isinstance(raw_state, int):
                    normalized = int(raw_state)
                elif allow_int_string and isinstance(raw_state, str) and raw_state.strip() != "":
                    try:
                        normalized = int(raw_state.strip())
                    except (TypeError, ValueError):
                        return None
                else:
                    return None
            else:
                if not isinstance(raw_state, str):
                    return None
                normalized = raw_state
            if normalized not in state_set:
                return None
            return normalized

        terminal_raw = params.get("terminal_states", [])
        terminal_states: set[object] = set()
        if isinstance(terminal_raw, list):
            for raw_terminal in terminal_raw:
                normalized_terminal = _coerce_state(raw_terminal, allow_int_string=False)
                if normalized_terminal is not None:
                    terminal_states.add(normalized_terminal)

        transitions: dict[object, tuple[list[object], list[float]]] = {}
        for raw_from, raw_targets in transitions_raw.items():
            from_state = _coerce_state(raw_from, allow_int_string=True)
            if from_state is None or not isinstance(raw_targets, dict) or len(raw_targets) == 0:
                continue
            targets: list[object] = []
            weights: list[float] = []
            for raw_to, raw_weight in raw_targets.items():
                to_state = _coerce_state(raw_to, allow_int_string=True)
                if to_state is None or to_state == from_state:
                    continue
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    continue
                if weight < 0:
                    continue
                targets.append(to_state)
                weights.append(weight)
            if targets and any(weight > 0 for weight in weights):
                transitions[from_state] = (targets, weights)

        current_state = _coerce_state(value, allow_int_string=(state_kind == "int"))
        if current_state is None:
            start_state_raw = params.get("start_state")
            current_state = _coerce_state(start_state_raw, allow_int_string=False)
        if current_state is None:
            current_state = states[0]

        steps = max(1, version_idx)
        for _ in range(steps):
            if current_state in terminal_states:
                continue
            transition = transitions.get(current_state)
            if transition is None:
                continue
            targets, weights = transition
            if not any(weight > 0 for weight in weights):
                continue
            current_state = rng.choices(targets, weights=weights, k=1)[0]
        return current_state

    if col.dtype == "int":
        try:
            if isinstance(value, bool):
                base = int(value)
            elif isinstance(value, int):
                base = value
            elif isinstance(value, float) and value.is_integer():
                base = int(value)
            elif isinstance(value, str) and value.strip() != "":
                base = int(value.strip())
            else:
                return value
        except (TypeError, ValueError):
            return value
        return base + version_idx
    if col.dtype in {"float", "decimal"}:
        base = float(value) if isinstance(value, (int, float)) else 0.0
        return round(base + (0.1 * version_idx), 6)
    if col.dtype == "text":
        base = str(value) if value is not None else "value"
        return f"{base}_v{version_idx}"
    if col.dtype == "bool":
        if value in {0, False}:
            return 1
        return 0
    if col.dtype == "date":
        try:
            d = date.fromisoformat(str(value))
        except Exception:
            d = date(2020, 1, 1)
        return _iso_date(d + timedelta(days=version_idx))
    if col.dtype == "datetime":
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return _iso_datetime(dt + timedelta(hours=version_idx))
    # Fallback for unsupported/rare types under tracking.
    return value


def _apply_scd2_history(
    table: TableSpec,
    rows: list[dict[str, object]],
    rng: random.Random,
    *,
    incoming_fks: list[ForeignKeySpec] | None = None,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    if not table.scd_active_from_column or not table.scd_active_to_column:
        raise ValueError(
            f"Table '{table.table_name}': scd2 generation requires scd_active_from_column and scd_active_to_column. "
            "Fix: set both active period columns in table config."
        )

    col_map = _table_col_map(table)
    pk_col = _table_pk_col_name(table)
    tracked_cols = _effective_scd_tracked_columns(table)
    static_cols = list(table.business_key_static_columns or [])
    start_col = table.scd_active_from_column
    end_col = table.scd_active_to_column
    active_dtype = col_map[start_col].dtype

    # For child-table SCD2, duplicate versions only when FK max_children capacity remains.
    fk_spare_capacity: list[tuple[ForeignKeySpec, dict[object, int]]] = []
    incoming_fks = list(incoming_fks or [])
    for fk in incoming_fks:
        counts_by_parent: dict[object, int] = {}
        for row in rows:
            parent_id = row.get(fk.child_column)
            counts_by_parent[parent_id] = counts_by_parent.get(parent_id, 0) + 1
        spare_by_parent = {
            parent_id: max(0, fk.max_children - count)
            for parent_id, count in counts_by_parent.items()
        }
        fk_spare_capacity.append((fk, spare_by_parent))

    expanded: list[dict[str, object]] = []

    for row_idx, base_row in enumerate(rows, start=1):
        # Deterministic behavior: every even key attempts a second version.
        # For child-table SCD2, we only duplicate when FK capacity allows it.
        allow_extra_version = True
        for fk, spare_by_parent in fk_spare_capacity:
            parent_id = base_row.get(fk.child_column)
            if spare_by_parent.get(parent_id, 0) <= 0:
                allow_extra_version = False
                break
        version_count = 2 if (row_idx % 2 == 0 and allow_extra_version) else 1
        if version_count > 1:
            for fk, spare_by_parent in fk_spare_capacity:
                parent_id = base_row.get(fk.child_column)
                spare_by_parent[parent_id] = max(0, spare_by_parent.get(parent_id, 0) - 1)
        base_offset_days = row_idx * 90

        for version_idx in range(version_count):
            out_row = dict(base_row)
            if version_idx > 0:
                for tracked_col in tracked_cols:
                    out_row[tracked_col] = _mutate_scd_tracked_value(
                        col_map[tracked_col],
                        out_row.get(tracked_col),
                        version_idx=version_idx,
                        rng=rng,
                    )
            for static_col in static_cols:
                out_row[static_col] = base_row.get(static_col)

            if active_dtype == "date":
                period_start = date(2020, 1, 1) + timedelta(days=base_offset_days + (version_idx * 30))
                if version_idx < version_count - 1:
                    next_start = date(2020, 1, 1) + timedelta(days=base_offset_days + ((version_idx + 1) * 30))
                    period_end = next_start - timedelta(days=1)
                    out_row[end_col] = _iso_date(period_end)
                else:
                    out_row[end_col] = "9999-12-31"
                out_row[start_col] = _iso_date(period_start)
            else:
                period_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                    days=base_offset_days + (version_idx * 30)
                )
                if version_idx < version_count - 1:
                    next_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                        days=base_offset_days + ((version_idx + 1) * 30)
                    )
                    period_end_dt = next_start_dt - timedelta(seconds=1)
                    out_row[end_col] = _iso_datetime(period_end_dt)
                else:
                    out_row[end_col] = "9999-12-31T23:59:59Z"
                out_row[start_col] = _iso_datetime(period_start_dt)

            expanded.append(out_row)

    for i, row in enumerate(expanded, start=1):
        row[pk_col] = i

    return expanded


def _apply_scd2_history_presized(
    table: TableSpec,
    rows: list[dict[str, object]],
    rng: random.Random,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    key_cols = list(table.business_key or [])
    if not key_cols:
        return rows

    if not table.scd_active_from_column or not table.scd_active_to_column:
        raise ValueError(
            f"Table '{table.table_name}': scd2 generation requires scd_active_from_column and scd_active_to_column. "
            "Fix: set both active period columns in table config."
        )

    col_map = _table_col_map(table)
    pk_col = _table_pk_col_name(table)
    tracked_cols = _effective_scd_tracked_columns(table)
    static_cols = list(table.business_key_static_columns or [])
    start_col = table.scd_active_from_column
    end_col = table.scd_active_to_column
    active_dtype = col_map[start_col].dtype

    counts_by_key: dict[tuple[object, ...], int] = {}
    base_row_by_key: dict[tuple[object, ...], dict[str, object]] = {}
    key_order: list[tuple[object, ...]] = []
    for row in rows:
        key = tuple(row.get(col) for col in key_cols)
        if key not in counts_by_key:
            counts_by_key[key] = 0
            key_order.append(key)
            base_row_by_key[key] = dict(row)
        counts_by_key[key] += 1

    key_offsets = {key: idx for idx, key in enumerate(key_order, start=1)}
    seen_by_key: dict[tuple[object, ...], int] = {}
    expanded: list[dict[str, object]] = []

    for row in rows:
        key = tuple(row.get(col) for col in key_cols)
        version_idx = seen_by_key.get(key, 0)
        seen_by_key[key] = version_idx + 1
        version_count = counts_by_key[key]
        base_row = base_row_by_key[key]

        out_row = dict(row)
        if version_idx > 0:
            for tracked_col in tracked_cols:
                out_row[tracked_col] = _mutate_scd_tracked_value(
                    col_map[tracked_col],
                    base_row.get(tracked_col),
                    version_idx=version_idx,
                    rng=rng,
                )
        for static_col in static_cols:
            out_row[static_col] = base_row.get(static_col)

        base_offset_days = key_offsets[key] * 90
        if active_dtype == "date":
            period_start = date(2020, 1, 1) + timedelta(days=base_offset_days + (version_idx * 30))
            if version_idx < version_count - 1:
                next_start = date(2020, 1, 1) + timedelta(days=base_offset_days + ((version_idx + 1) * 30))
                out_row[end_col] = _iso_date(next_start - timedelta(days=1))
            else:
                out_row[end_col] = "9999-12-31"
            out_row[start_col] = _iso_date(period_start)
        else:
            period_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                days=base_offset_days + (version_idx * 30)
            )
            if version_idx < version_count - 1:
                next_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                    days=base_offset_days + ((version_idx + 1) * 30)
                )
                out_row[end_col] = _iso_datetime(next_start_dt - timedelta(seconds=1))
            else:
                out_row[end_col] = "9999-12-31T23:59:59Z"
            out_row[start_col] = _iso_datetime(period_start_dt)

        expanded.append(out_row)

    for i, row in enumerate(expanded, start=1):
        row[pk_col] = i
    return expanded


def _apply_business_key_and_scd(
    table: TableSpec,
    rows: list[dict[str, object]],
    rng: random.Random,
    *,
    incoming_fks: list[ForeignKeySpec] | None = None,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    if table.business_key_unique_count is None:
        _enforce_business_key_uniqueness(table, rows)
    else:
        _enforce_business_key_unique_count(table, rows)

    scd_mode = _normalize_scd_mode(table)
    if scd_mode == "scd1" and table.business_key_unique_count is not None:
        key_cols = list(table.business_key or [])
        key_tuples = {tuple(row.get(col) for col in key_cols) for row in rows}
        if len(key_tuples) != len(rows):
            raise ValueError(
                f"Table '{table.table_name}': scd_mode='scd1' requires one row per business key, but generated rows ({len(rows)}) exceed unique business keys ({len(key_tuples)}). "
                "Fix: set business_key_unique_count equal to row_count for SCD1 tables."
            )
    if scd_mode == "scd2":
        if table.business_key_unique_count is not None:
            return _apply_scd2_history_presized(table, rows, rng)
        return _apply_scd2_history(table, rows, rng, incoming_fks=incoming_fks)
    return rows


def _compile_parent_cache_columns(
    project: SchemaProject,
    *,
    compiled_timeline_constraints: dict[str, list[dict[str, object]]],
) -> dict[str, set[str]]:
    required_by_table: dict[str, set[str]] = {}
    for fk in project.foreign_keys:
        cols = required_by_table.setdefault(fk.parent_table, set())
        cols.add(fk.parent_column)
        raw_profile = fk.parent_selection
        if isinstance(raw_profile, dict):
            attr_raw = raw_profile.get("parent_attribute")
            if isinstance(attr_raw, str) and attr_raw.strip() != "":
                cols.add(attr_raw.strip())

    for rules in compiled_timeline_constraints.values():
        for rule in rules:
            references = rule.get("references")
            if not isinstance(references, list):
                continue
            for raw_reference in references:
                if not isinstance(raw_reference, dict):
                    continue
                parent_table = str(raw_reference.get("parent_table", "")).strip()
                parent_column = str(raw_reference.get("parent_column", "")).strip()
                parent_pk_column = str(raw_reference.get("parent_pk_column", "")).strip()
                if parent_table == "":
                    continue
                cols = required_by_table.setdefault(parent_table, set())
                if parent_column != "":
                    cols.add(parent_column)
                if parent_pk_column != "":
                    cols.add(parent_pk_column)
    return required_by_table


def _cache_parent_rows(
    rows: list[dict[str, object]],
    *,
    required_columns: set[str],
) -> list[dict[str, object]]:
    if not required_columns:
        return rows
    cached_rows: list[dict[str, object]] = []
    for row in rows:
        cached_row: dict[str, object] = {}
        for column_name in required_columns:
            cached_row[column_name] = row.get(column_name)
        cached_rows.append(cached_row)
    return cached_rows


def _generate_project_rows_internal(
    project: SchemaProject,
    *,
    retain_rows: bool,
    on_table_rows: Callable[[str, list[dict[str, object]]], None] | None = None,
) -> dict[str, list[dict[str, object]]]:
    reset_runtime_generator_state()
    validate_project(project)
    effective_project = _resolve_sample_profile_fits(project)
    validate_project(effective_project)
    compiled_timeline_constraints = _compile_timeline_constraints(effective_project)
    compiled_data_quality_profiles = _compile_data_quality_profiles(effective_project)
    compiled_locale_identity_bundles = _compile_locale_identity_bundles(effective_project)
    locale_bundle_state: dict[str, dict[tuple[str, object], dict[str, object]]] = {}

    table_map: dict[str, TableSpec] = {t.table_name: t for t in effective_project.tables}

    fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    for fk in effective_project.foreign_keys:
        fks_by_child.setdefault(fk.child_table, []).append(fk)

    parent_cache_columns = _compile_parent_cache_columns(
        effective_project,
        compiled_timeline_constraints=compiled_timeline_constraints,
    )
    remaining_parent_consumers: dict[str, int] = {table.table_name: 0 for table in effective_project.tables}
    for fk in effective_project.foreign_keys:
        remaining_parent_consumers[fk.parent_table] = remaining_parent_consumers.get(fk.parent_table, 0) + 1

    related_by_table = compiled_locale_identity_bundles.get("related_by_table")
    remaining_related_bundle_consumers: dict[str, int] = {}
    if isinstance(related_by_table, dict):
        for specs in related_by_table.values():
            if not isinstance(specs, list):
                continue
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                bundle_id = str(spec.get("bundle_id", "")).strip()
                if bundle_id == "":
                    continue
                remaining_related_bundle_consumers[bundle_id] = (
                    remaining_related_bundle_consumers.get(bundle_id, 0) + 1
                )

    order = _dependency_order(effective_project)
    parent_rows_by_table: dict[str, list[dict[str, object]]] = {}
    retained_rows_by_table: dict[str, list[dict[str, object]]] = {}

    def _assign_fk_column(
        rng: random.Random,
        rows: list[dict[str, object]],
        child_fk_col: str,
        parent_ids: list[int],
        min_children: int,
        max_children: int,
        *,
        child_table: str,
        parent_table: str,
        parent_weights: list[float] | None = None,
        extra_level_weights: list[float] | None = None,
    ) -> None:
        """
        Assign rows[*][child_fk_col] such that each parent_id appears between min_children and max_children times.

        This requires:
            len(parent_ids) * min_children <= len(rows) <= len(parent_ids) * max_children
        """
        location = f"Table '{child_table}', FK column '{child_fk_col}'"
        counts = _allocate_fk_child_counts(
            rng,
            parent_ids=parent_ids,
            min_children=min_children,
            max_children=max_children,
            total_children=len(rows),
            location=location,
            parent_weights=parent_weights,
            extra_level_weights=extra_level_weights,
        )

        # Build the pool
        pool: list[int] = []
        for pid, k in zip(parent_ids, counts, strict=True):
            pool.extend([pid] * k)

        rng.shuffle(pool)

        # Assign
        for r, pid in zip(rows, pool, strict=True):
            r[child_fk_col] = pid

    def _record_table_rows(
        table_name: str,
        rows: list[dict[str, object]],
    ) -> None:
        if retain_rows:
            retained_rows_by_table[table_name] = rows
        if on_table_rows is not None:
            on_table_rows(table_name, rows)

        if remaining_parent_consumers.get(table_name, 0) <= 0:
            parent_rows_by_table.pop(table_name, None)
            return

        required_columns = set(parent_cache_columns.get(table_name, set()))
        if not required_columns:
            parent_rows_by_table[table_name] = rows
            return
        parent_rows_by_table[table_name] = _cache_parent_rows(rows, required_columns=required_columns)

    def _release_parent_rows_for_consumed_fks(
        incoming_fks: list[ForeignKeySpec],
    ) -> None:
        for fk in incoming_fks:
            parent_name = fk.parent_table
            remaining = remaining_parent_consumers.get(parent_name, 0) - 1
            remaining_parent_consumers[parent_name] = max(0, remaining)
            if remaining_parent_consumers[parent_name] == 0:
                parent_rows_by_table.pop(parent_name, None)

    def _release_bundle_state_after_related_table(table_name: str) -> None:
        if not isinstance(related_by_table, dict):
            return
        related_specs = related_by_table.get(table_name, [])
        if isinstance(related_specs, list):
            for spec in related_specs:
                if not isinstance(spec, dict):
                    continue
                bundle_id = str(spec.get("bundle_id", "")).strip()
                if bundle_id == "":
                    continue
                remaining = remaining_related_bundle_consumers.get(bundle_id, 0) - 1
                remaining_related_bundle_consumers[bundle_id] = max(0, remaining)
        for bundle_id in list(locale_bundle_state.keys()):
            if remaining_related_bundle_consumers.get(bundle_id, 0) <= 0:
                locale_bundle_state.pop(bundle_id, None)

    for table_name in order:
        t = table_map[table_name]
        rng = random.Random(_stable_subseed(effective_project.seed, f"table:{table_name}"))

        pk_col = _table_pk_col_name(t)
        incoming_fks = fks_by_child.get(table_name, [])
        ordered_cols = _order_columns_by_dependencies(t.columns)

        # -------------------------
        # ROOT TABLE (no incoming FK)
        # -------------------------
        if not incoming_fks:
            n = t.row_count
            rows: list[dict[str, object]] = []

            for i in range(1, n + 1):
                row: dict[str, object] = {}
                for col in ordered_cols:
                    row[col.name] = _gen_value(col, rng, i, table_name, row)

                rows.append(row)

            _apply_table_correlation_groups(t, rows, project_seed=effective_project.seed)
            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
            _enforce_table_timeline_constraints(
                t,
                rows,
                results=parent_rows_by_table,
                compiled_constraints=compiled_timeline_constraints,
            )
            _apply_table_locale_identity_bundles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_bundles=compiled_locale_identity_bundles,
                bundle_state=locale_bundle_state,
            )
            _apply_table_data_quality_profiles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_profiles=compiled_data_quality_profiles,
            )

            # Defensive: ensure PK exists
            for r in rows:
                if r.get(pk_col) is None:
                    raise ValueError(
                        _runtime_error(
                            f"Table '{table_name}', column '{pk_col}'",
                            "primary key generated as null",
                            "set PK column nullable=false and use deterministic PK generation",
                        )
                    )

            # Extra defensive fill (should not normally trigger)
            for i, r in enumerate(rows, start=1):
                if r.get(pk_col) is None:
                    r[pk_col] = i

            _record_table_rows(table_name, rows)
            _release_bundle_state_after_related_table(table_name)
            logger.info("Generated root table '%s' rows=%d", table_name, len(rows))
            continue

        # -----------------------------------------
        # CHILD TABLE with exactly ONE incoming FK
        # -----------------------------------------
        if len(incoming_fks) == 1:
            fk = incoming_fks[0]
            parent_table_name = fk.parent_table
            parent_rows, parent_ids = _fk_parent_rows_and_ids(
                fk,
                results=parent_rows_by_table,
                child_table=table_name,
            )
            parent_weights = _build_fk_parent_weights(
                fk,
                parent_rows=parent_rows,
                child_table=table_name,
            )
            distribution = _normalize_fk_child_count_distribution(
                fk,
                child_table=table_name,
            )
            fk_location = f"Table '{table_name}', FK column '{fk.child_column}'"
            extra_capacity = fk.max_children - fk.min_children
            extra_weights, extra_level_weights = _compile_fk_distribution_weights(
                distribution,
                extra_capacity=extra_capacity,
                location=fk_location,
            )

            rows: list[dict[str, object]] = []
            next_pk = 1

            if parent_weights is None:
                if distribution is None:
                    for pid in parent_ids:
                        k = rng.randint(fk.min_children, fk.max_children)
                        for _ in range(k):
                            row: dict[str, object] = {}
                            for col in ordered_cols:
                                if col.name == fk.child_column:
                                    row[col.name] = pid
                                else:
                                    row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                            rows.append(row)
                            next_pk += 1
                else:
                    extra_choices = list(range(extra_capacity + 1))
                    for pid in parent_ids:
                        if extra_capacity > 0 and extra_weights is not None:
                            extra = int(rng.choices(extra_choices, weights=extra_weights, k=1)[0])
                        else:
                            extra = 0
                        k = fk.min_children + extra
                        for _ in range(k):
                            row: dict[str, object] = {}
                            for col in ordered_cols:
                                if col.name == fk.child_column:
                                    row[col.name] = pid
                                else:
                                    row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                            rows.append(row)
                            next_pk += 1
            else:
                requested_extras = _sample_requested_fk_extras(
                    rng,
                    parent_count=len(parent_ids),
                    extra_capacity=extra_capacity,
                    extra_weights=extra_weights,
                )
                positive_extra_capacity = sum(
                    extra_capacity
                    for weight in parent_weights
                    if weight > 0
                )
                min_total = len(parent_ids) * fk.min_children
                total_children = min_total + min(requested_extras, positive_extra_capacity)
                counts = _allocate_fk_child_counts(
                    rng,
                    parent_ids=parent_ids,
                    min_children=fk.min_children,
                    max_children=fk.max_children,
                    total_children=total_children,
                    location=fk_location,
                    parent_weights=parent_weights,
                    extra_level_weights=extra_level_weights,
                )
                for pid, k in zip(parent_ids, counts, strict=True):
                    for _ in range(k):
                        row = {}
                        for col in ordered_cols:
                            if col.name == fk.child_column:
                                row[col.name] = pid
                            else:
                                row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                        rows.append(row)
                        next_pk += 1

            _apply_table_correlation_groups(t, rows, project_seed=effective_project.seed)
            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
            _enforce_table_timeline_constraints(
                t,
                rows,
                results=parent_rows_by_table,
                compiled_constraints=compiled_timeline_constraints,
            )
            _apply_table_locale_identity_bundles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_bundles=compiled_locale_identity_bundles,
                bundle_state=locale_bundle_state,
            )
            _apply_table_data_quality_profiles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_profiles=compiled_data_quality_profiles,
            )
            _record_table_rows(table_name, rows)
            _release_parent_rows_for_consumed_fks(incoming_fks)
            _release_bundle_state_after_related_table(table_name)
            logger.info(
                "Generated child table '%s' rows=%d (parent=%s rows=%d, per-parent=%d..%d)",
                table_name, len(rows), parent_table_name, len(parent_ids), fk.min_children, fk.max_children
            )
            continue

        # -----------------------------------------
        # CHILD TABLE with MULTIPLE incoming FKs
        # Strategy: generate total rows = t.row_count, then assign each FK column.
        # -----------------------------------------
        # Compute allowed range intersection across all incoming FKs
        fk_parent_specs: list[tuple[ForeignKeySpec, list[dict[str, object]], list[int]]] = []
        mins = []
        maxs = []
        for fk in incoming_fks:
            parent_rows, parent_ids = _fk_parent_rows_and_ids(
                fk,
                results=parent_rows_by_table,
                child_table=table_name,
            )
            fk_parent_specs.append((fk, parent_rows, parent_ids))
            mins.append(len(parent_ids) * fk.min_children)
            maxs.append(len(parent_ids) * fk.max_children)

        min_allowed = max(mins)
        max_allowed = min(maxs)

        if max_allowed < min_allowed:
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}'",
                    f"FK constraints produce an empty row_count range (min_allowed={min_allowed}, max_allowed={max_allowed})",
                    "adjust FK min_children/max_children so ranges overlap",
                )
            )

        # If user set row_count > 0, use it; else auto-pick a value in the intersection
        if t.row_count and t.row_count > 0:
            n = t.row_count
            if not (min_allowed <= n <= max_allowed):
                raise ValueError(
                    _runtime_error(
                        f"Table '{table_name}'",
                        f"row_count={n} is outside FK-constrained range [{min_allowed}, {max_allowed}]",
                        "set row_count within the allowed range or adjust FK bounds",
                    )
                )
        else:
            n = rng.randint(min_allowed, max_allowed)


        fk_cols = {fk.child_column for fk in incoming_fks}

        rows: list[dict[str, object]] = []
        for i in range(1, n + 1):
            row: dict[str, object] = {}
            for col in ordered_cols:
                if col.name in fk_cols:
                    # placeholder; we'll assign after parents exist
                    row[col.name] = None
                else:
                    row[col.name] = _gen_value(col, rng, i, table_name, row)
            rows.append(row)

        # Defensive: ensure PK exists
        for r in rows:
            if r.get(pk_col) is None:
                raise ValueError(
                    _runtime_error(
                        f"Table '{table_name}', column '{pk_col}'",
                        "primary key generated as null",
                        "set PK column nullable=false and use deterministic PK generation",
                    )
                )

        # Assign each FK column independently, enforcing its min/max rules
        for fk, parent_rows, parent_ids in fk_parent_specs:
            parent_weights = _build_fk_parent_weights(
                fk,
                parent_rows=parent_rows,
                child_table=table_name,
            )
            distribution = _normalize_fk_child_count_distribution(
                fk,
                child_table=table_name,
            )
            _, extra_level_weights = _compile_fk_distribution_weights(
                distribution,
                extra_capacity=(fk.max_children - fk.min_children),
                location=f"Table '{table_name}', FK column '{fk.child_column}'",
            )
            # Use a stable subseed per FK so results are repeatable
            fk_rng = random.Random(
                _stable_subseed(
                    effective_project.seed,
                    f"fk:{table_name}:{fk.child_column}:{fk.parent_table}",
                )
            )

            _assign_fk_column(
                fk_rng,
                rows,
                fk.child_column,
                parent_ids,
                fk.min_children,
                fk.max_children,
                child_table=table_name,
                parent_table=fk.parent_table,
                parent_weights=parent_weights,
                extra_level_weights=extra_level_weights,
            )

        _apply_table_correlation_groups(t, rows, project_seed=effective_project.seed)
        rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
        _enforce_table_timeline_constraints(
            t,
            rows,
            results=parent_rows_by_table,
            compiled_constraints=compiled_timeline_constraints,
        )
        _apply_table_locale_identity_bundles(
            t,
            rows,
            project_seed=effective_project.seed,
            compiled_bundles=compiled_locale_identity_bundles,
            bundle_state=locale_bundle_state,
        )
        _apply_table_data_quality_profiles(
            t,
            rows,
            project_seed=effective_project.seed,
            compiled_profiles=compiled_data_quality_profiles,
        )
        _record_table_rows(table_name, rows)
        _release_parent_rows_for_consumed_fks(incoming_fks)
        _release_bundle_state_after_related_table(table_name)

        logger.info(
            "Generated multi-FK child table '%s' rows=%d (incoming_fks=%d)",
            table_name, len(rows), len(incoming_fks)
        )

    return retained_rows_by_table


def generate_project_rows(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    """
    Generates rows for all tables with valid PK/FK according to the project's foreign key rules.

    Returns: dict of table_name -> list of row dicts
    """
    return _generate_project_rows_internal(project, retain_rows=True)


def generate_project_rows_streaming(
    project: SchemaProject,
    *,
    on_table_rows: Callable[[str, list[dict[str, object]]], None],
) -> None:
    """
    Generate rows in deterministic table order and emit each table's rows via callback.
    Rows are not retained globally, enabling bounded-memory export flows.
    """
    _generate_project_rows_internal(
        project,
        retain_rows=False,
        on_table_rows=on_table_rows,
    )

def _order_columns_by_dependencies(cols: list[ColumnSpec]) -> list[ColumnSpec]:
    """
    Topological-ish ordering for column dependencies within a row.
    - columns without depends_on first
    - then columns whose deps are satisfied
    Raises on cycles / missing deps.
    """
    remaining = list(cols)
    ordered: list[ColumnSpec] = []
    produced: set[str] = set()

    # pre-seed: treat columns with no depends as ready
    while remaining:
        progressed = False
        for c in list(remaining):
            deps = getattr(c, "depends_on", None) or []
            if all(d in produced for d in deps):
                ordered.append(c)
                produced.add(c.name)
                remaining.remove(c)
                progressed = True
        if not progressed:
            # cycle or missing dependency
            stuck = [(c.name, getattr(c, "depends_on", None)) for c in remaining]
            raise ValueError(
                _runtime_error(
                    "Column dependency ordering",
                    f"cannot resolve dependencies {stuck}",
                    "remove circular depends_on references and reference only existing columns",
                )
            )
    return ordered
