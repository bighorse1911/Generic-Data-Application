from __future__ import annotations

import base64

DTYPES = ["int", "decimal", "text", "bool", "date", "datetime", "bytes"]
GENERATORS = [
    "",
    "sample_csv",
    "if_then",
    "derived_expr",
    "time_offset",
    "hierarchical_category",
    "uniform_int",
    "uniform_float",
    "normal",
    "lognormal",
    "choice_weighted",
    "ordered_choice",
    "state_transition",
    "date",
    "timestamp_utc",
    "latitude",
    "longitude",
    "money",
    "percent",
]
GENERATOR_VALID_DTYPES: dict[str, set[str]] = {
    "sample_csv": {"int", "decimal", "text"},
    "if_then": {"int", "decimal", "text", "bool", "date", "datetime"},
    "derived_expr": {"int", "decimal", "text", "bool", "date", "datetime"},
    "time_offset": {"date", "datetime"},
    "hierarchical_category": {"text"},
    "uniform_int": {"int"},
    "uniform_float": {"decimal"},
    "normal": {"int", "decimal"},
    "lognormal": {"int", "decimal"},
    "choice_weighted": {"int", "text"},
    "ordered_choice": {"int", "text"},
    "state_transition": {"text", "int"},
    "date": {"date"},
    "timestamp_utc": {"datetime"},
    "latitude": {"decimal"},
    "longitude": {"decimal"},
    "money": {"decimal"},
    "percent": {"decimal"},
}
PATTERN_PRESET_CUSTOM = "(custom)"
PATTERN_PRESETS: dict[str, str | None] = {
    PATTERN_PRESET_CUSTOM: None,
    "Lowercase word (5-14)": r"^[a-z]{5,14}$",
    "Uppercase code (3-8)": r"^[A-Z]{3,8}$",
    "Alphanumeric ID (6-12)": r"^[A-Za-z0-9]{6,12}$",
    "US ZIP (5)": r"^\d{5}$",
    "Email (basic)": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
}
def valid_generators_for_dtype(dtype: str) -> list[str]:
    selected_dtype = dtype.strip().lower()
    if selected_dtype == "":
        return [""]
    valid = [""]
    for generator in GENERATORS:
        if generator == "":
            continue
        if selected_dtype in GENERATOR_VALID_DTYPES.get(generator, set()):
            valid.append(generator)
    return valid
def default_generator_params_template(generator: str, dtype: str) -> dict[str, object] | None:
    key = generator.strip()
    selected_dtype = dtype.strip().lower()
    if key == "sample_csv":
        return {"path": "tests/fixtures/city_country_pool.csv", "column_index": 0}
    if key == "if_then":
        return {
            "if_column": "source_column",
            "operator": "==",
            "value": "A",
            "then_value": "B",
            "else_value": "C",
        }
    if key == "derived_expr":
        return {"expression": "base_amount - discount_amount"}
    if key == "time_offset":
        if selected_dtype == "datetime":
            return {
                "base_column": "base_timestamp",
                "direction": "after",
                "min_seconds": 0,
                "max_seconds": 3600,
            }
        return {
            "base_column": "base_date",
            "direction": "after",
            "min_days": 0,
            "max_days": 30,
        }
    if key == "hierarchical_category":
        return {
            "parent_column": "parent_category",
            "hierarchy": {"Parent": ["ChildA", "ChildB"]},
            "default_children": ["Other"],
        }
    if key == "uniform_int":
        return {"min": 0, "max": 100}
    if key == "uniform_float":
        return {"min": 0.0, "max": 1.0, "decimals": 3}
    if key == "normal":
        return {"mean": 0.0, "stdev": 1.0, "decimals": 2}
    if key == "lognormal":
        return {"median": 100.0, "sigma": 0.5, "decimals": 2}
    if key == "choice_weighted":
        return {"choices": ["A", "B"], "weights": [0.8, 0.2]}
    if key == "ordered_choice":
        return {
            "orders": {"A": ["choice_1", "choice_2", "choice_3"], "B": ["choice_4", "choice_5", "choice_6"]},
            "order_weights": {"A": 0.7, "B": 0.3},
            "move_weights": [0.1, 0.8, 0.1],
            "start_index": 0,
        }
    if key == "state_transition":
        if selected_dtype == "int":
            return {
                "entity_column": "entity_id",
                "states": [0, 1, 2],
                "start_state": 0,
                "transitions": {"0": {"1": 1.0}, "1": {"2": 1.0}},
                "terminal_states": [2],
                "dwell_min": 1,
                "dwell_max": 1,
            }
        return {
            "entity_column": "entity_id",
            "states": ["new", "active", "closed"],
            "start_state": "new",
            "transitions": {"new": {"active": 1.0}, "active": {"closed": 1.0}},
            "terminal_states": ["closed"],
            "dwell_min": 1,
            "dwell_max": 1,
        }
    if key == "date":
        return {"start": "2020-01-01", "end": "2026-12-31"}
    if key == "timestamp_utc":
        return {"start": "2020-01-01T00:00:00Z", "end": "2026-12-31T23:59:59Z"}
    if key == "latitude":
        return {"min": -90.0, "max": 90.0, "decimals": 6}
    if key == "longitude":
        return {"min": -180.0, "max": 180.0, "decimals": 6}
    if key == "money":
        return {"min": 0.0, "max": 10000.0, "decimals": 2}
    if key == "percent":
        return {"min": 0.0, "max": 100.0, "decimals": 2}
    return None
SCD_MODES = ["", "scd1", "scd2"]
EXPORT_OPTION_CSV = "CSV (folder)"
EXPORT_OPTION_SQLITE = "SQLite (database)"
EXPORT_OPTIONS = [EXPORT_OPTION_CSV, EXPORT_OPTION_SQLITE]
def validate_export_option(option: object) -> str:
    value = option.strip() if isinstance(option, str) else ""
    if value in EXPORT_OPTIONS:
        return value
    allowed = ", ".join(EXPORT_OPTIONS)
    raise ValueError(
        "Generate / Preview / Export / SQLite panel: unsupported export option "
        f"'{option}'. Fix: choose one of: {allowed}."
    )

def _gui_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."

def _csv_export_value(value: object) -> object:
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value

__all__ = [
    "DTYPES",
    "GENERATORS",
    "GENERATOR_VALID_DTYPES",
    "PATTERN_PRESET_CUSTOM",
    "PATTERN_PRESETS",
    "SCD_MODES",
    "EXPORT_OPTION_CSV",
    "EXPORT_OPTION_SQLITE",
    "EXPORT_OPTIONS",
    "valid_generators_for_dtype",
    "default_generator_params_template",
    "validate_export_option",
    "_gui_error",
    "_csv_export_value",
]
