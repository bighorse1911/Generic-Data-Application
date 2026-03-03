from __future__ import annotations

import math

from src.schema.types import SchemaProject
from src.schema.types import TableSpec
from src.schema.validators.common import _validation_error

def _validate_fk_child_count_distribution(
    raw_profile: object,
    *,
    location: str,
) -> None:
    if not isinstance(raw_profile, dict):
        raise ValueError(
            _validation_error(
                location,
                "child_count_distribution must be a JSON object when provided",
                "set child_count_distribution to an object with type and optional shape parameters",
            )
        )

    type_raw = raw_profile.get("type")
    if not isinstance(type_raw, str) or type_raw.strip() == "":
        raise ValueError(
            _validation_error(
                location,
                "child_count_distribution.type is required",
                "set type to one of: uniform, poisson, zipf",
            )
        )
    dist_type = type_raw.strip().lower()
    if dist_type not in {"uniform", "poisson", "zipf"}:
        raise ValueError(
            _validation_error(
                location,
                f"unsupported child_count_distribution.type '{type_raw}'",
                "set type to one of: uniform, poisson, zipf",
            )
        )

    if dist_type == "poisson":
        lam_raw = raw_profile.get("lambda")
        if lam_raw is None:
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.lambda is required for type='poisson'",
                    "set lambda to a positive numeric value",
                )
            )
        if isinstance(lam_raw, bool):
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.lambda must be numeric",
                    "set lambda to a positive numeric value",
                )
            )
        try:
            lam = float(lam_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.lambda must be numeric",
                    "set lambda to a positive numeric value",
                )
            ) from exc
        if (not math.isfinite(lam)) or lam <= 0.0:
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.lambda must be a finite value > 0",
                    "set lambda to a positive numeric value",
                )
            )
    elif dist_type == "zipf":
        s_raw = raw_profile.get("s")
        if s_raw is None:
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.s is required for type='zipf'",
                    "set s to a positive numeric value (for example 1.2)",
                )
            )
        if isinstance(s_raw, bool):
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.s must be numeric",
                    "set s to a positive numeric value (for example 1.2)",
                )
            )
        try:
            s_value = float(s_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.s must be numeric",
                    "set s to a positive numeric value (for example 1.2)",
                )
            ) from exc
        if (not math.isfinite(s_value)) or s_value <= 0.0:
            raise ValueError(
                _validation_error(
                    location,
                    "child_count_distribution.s must be a finite value > 0",
                    "set s to a positive numeric value (for example 1.2)",
                )
            )


def validate_foreign_keys(project: SchemaProject, *, table_map: dict[str, TableSpec]) -> None:
    for fk in project.foreign_keys:
        if fk.child_table not in table_map:
            raise ValueError(
                f"Foreign key: child_table '{fk.child_table}' not found. "
                "Fix: use an existing table name for child_table."
            )
        if fk.parent_table not in table_map:
            raise ValueError(
                f"Foreign key: parent_table '{fk.parent_table}' not found. "
                "Fix: use an existing table name for parent_table."
            )

        child_table = table_map[fk.child_table]
        parent_table = table_map[fk.parent_table]
        child_cols = {c.name: c for c in child_table.columns}
        parent_cols = {c.name: c for c in parent_table.columns}

        if fk.child_column not in child_cols:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': child_column '{fk.child_column}' not found. "
                "Fix: use an existing child column."
            )
        if fk.parent_column not in parent_cols:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': parent_column '{fk.parent_column}' not found. "
                "Fix: use an existing parent column."
            )
        if not parent_cols[fk.parent_column].primary_key:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': parent column '{fk.parent_table}.{fk.parent_column}' must be primary key. "
                "Fix: reference the parent table primary key column."
            )
        if child_cols[fk.child_column].dtype != "int":
            raise ValueError(
                f"Foreign key on table '{fk.child_table}', column '{fk.child_column}': child FK column must be dtype int. "
                "Fix: use dtype='int' for FK child columns."
            )
        if fk.min_children <= 0 or fk.max_children <= 0:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': min_children and max_children must be > 0. "
                "Fix: set positive integer bounds."
            )
        if fk.min_children > fk.max_children:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': min_children cannot exceed max_children. "
                "Fix: set min_children <= max_children."
            )
        child_count_distribution = fk.child_count_distribution
        if child_count_distribution is not None:
            _validate_fk_child_count_distribution(
                child_count_distribution,
                location=f"Foreign key on table '{fk.child_table}', column '{fk.child_column}'",
            )
        parent_selection = fk.parent_selection
        if parent_selection is not None:
            location = f"Foreign key on table '{fk.child_table}', column '{fk.child_column}'"
            if not isinstance(parent_selection, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "parent_selection must be a JSON object when provided",
                        "set parent_selection to an object with parent_attribute, weights, and optional default_weight",
                    )
                )

            parent_attribute_raw = parent_selection.get("parent_attribute")
            if not isinstance(parent_attribute_raw, str) or parent_attribute_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "parent_selection.parent_attribute is required",
                        "set parent_selection.parent_attribute to an existing parent column name",
                    )
                )
            parent_attribute = parent_attribute_raw.strip()
            parent_attribute_col = parent_cols.get(parent_attribute)
            if parent_attribute_col is None:
                raise ValueError(
                    _validation_error(
                        location,
                        f"parent_selection.parent_attribute '{parent_attribute}' was not found on table '{fk.parent_table}'",
                        "use an existing parent table column name for parent_attribute",
                    )
                )
            if parent_attribute_col.dtype == "bytes":
                raise ValueError(
                    _validation_error(
                        location,
                        f"parent_selection.parent_attribute '{parent_attribute}' cannot use dtype bytes",
                        "use a non-bytes parent attribute column for weighted cohort selection",
                    )
                )

            weights_raw = parent_selection.get("weights")
            if not isinstance(weights_raw, dict) or len(weights_raw) == 0:
                raise ValueError(
                    _validation_error(
                        location,
                        "parent_selection.weights must be a non-empty object",
                        "set weights to a mapping of parent attribute values to non-negative numeric weights",
                    )
                )

            normalized_weights: dict[str, float] = {}
            for raw_key, raw_weight in weights_raw.items():
                if not isinstance(raw_key, str) or raw_key.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "parent_selection.weights contains an empty or non-string key",
                            "use non-empty string keys in parent_selection.weights",
                        )
                    )
                key = raw_key.strip()
                if key in normalized_weights:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"parent_selection.weights has duplicate key '{key}' after normalization",
                            "use unique weight keys in parent_selection.weights",
                        )
                    )
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"parent_selection.weights['{raw_key}'] must be numeric",
                            "use non-negative numeric values for parent_selection.weights",
                        )
                    ) from exc
                if (not math.isfinite(weight)) or weight < 0:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"parent_selection.weights['{raw_key}'] must be a finite value >= 0",
                            "use non-negative finite numeric weights",
                        )
                    )
                normalized_weights[key] = weight

            default_weight_raw = parent_selection.get("default_weight", 1.0)
            try:
                default_weight = float(default_weight_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _validation_error(
                        location,
                        "parent_selection.default_weight must be numeric when provided",
                        "set default_weight to a non-negative numeric value",
                    )
                ) from exc
            if (not math.isfinite(default_weight)) or default_weight < 0:
                raise ValueError(
                    _validation_error(
                        location,
                        "parent_selection.default_weight must be a finite value >= 0",
                        "set default_weight to a non-negative finite numeric value",
                    )
                )
            if default_weight <= 0 and not any(weight > 0 for weight in normalized_weights.values()):
                raise ValueError(
                    _validation_error(
                        location,
                        "parent_selection provides no positive selection weight",
                        "set at least one positive weight in weights or set default_weight > 0",
                    )
                )



__all__ = ["_validate_fk_child_count_distribution", "validate_foreign_keys"]
