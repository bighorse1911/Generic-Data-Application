"""v2-only generator form specs and parsing helpers for schema_project_v2."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal

ControlKind = Literal[
    "text",
    "int",
    "float",
    "combo",
    "column",
    "scalar",
    "csv_list",
    "float_list",
    "json_object",
    "path",
]


@dataclass(frozen=True)
class GeneratorFieldSpec:
    """One structured GUI field bound to a generator params key."""

    field_id: str
    label: str
    control_kind: ControlKind
    required: bool = False
    options: tuple[str, ...] = ()
    dependency_source: bool = False
    show_for_dtypes: tuple[str, ...] = ()
    hint: str = ""

    def is_visible_for_dtype(self, dtype: str) -> bool:
        if not self.show_for_dtypes:
            return True
        return dtype.strip().lower() in {d.strip().lower() for d in self.show_for_dtypes}


@dataclass(frozen=True)
class GeneratorFormSpec:
    """Structured GUI contract for a specific generator."""

    generator_id: str
    fields: tuple[GeneratorFieldSpec, ...]
    description: str = ""


@dataclass(frozen=True)
class GeneratorFormState:
    """Split params into known form-managed keys and passthrough unknown keys."""

    known_params: dict[str, object] = field(default_factory=dict)
    passthrough_params: dict[str, object] = field(default_factory=dict)
    validation_errors: tuple[str, ...] = ()


CROSS_CUTTING_FIELDS: tuple[GeneratorFieldSpec, ...] = (
    GeneratorFieldSpec(
        field_id="null_rate",
        label="Null rate",
        control_kind="float",
        hint="Optional 0.0-1.0 probability of null output.",
    ),
    GeneratorFieldSpec(
        field_id="outlier_rate",
        label="Outlier rate",
        control_kind="float",
        hint="Optional outlier injection probability.",
    ),
    GeneratorFieldSpec(
        field_id="outlier_scale",
        label="Outlier scale",
        control_kind="float",
        hint="Optional outlier magnitude scaling.",
    ),
    GeneratorFieldSpec(
        field_id="min_length",
        label="Bytes min length",
        control_kind="int",
        show_for_dtypes=("bytes",),
        hint="Applies to bytes columns.",
    ),
    GeneratorFieldSpec(
        field_id="max_length",
        label="Bytes max length",
        control_kind="int",
        show_for_dtypes=("bytes",),
        hint="Applies to bytes columns.",
    ),
)


GENERATOR_FORM_SPECS: dict[str, GeneratorFormSpec] = {
    "sample_csv": GeneratorFormSpec(
        generator_id="sample_csv",
        description="Empirical CSV sampling.",
        fields=(
            GeneratorFieldSpec("path", "CSV path", "path", required=True),
            GeneratorFieldSpec("column_index", "Column index", "int"),
            GeneratorFieldSpec(
                "match_column",
                "Match source column",
                "column",
                dependency_source=True,
            ),
            GeneratorFieldSpec("match_column_index", "Match column index", "int"),
        ),
    ),
    "if_then": GeneratorFormSpec(
        generator_id="if_then",
        description="Conditional branch from another column.",
        fields=(
            GeneratorFieldSpec(
                "if_column",
                "If column",
                "column",
                required=True,
                dependency_source=True,
            ),
            GeneratorFieldSpec(
                "operator",
                "Operator",
                "combo",
                options=("==", "!="),
            ),
            GeneratorFieldSpec("value", "If value", "scalar", required=True),
            GeneratorFieldSpec("then_value", "Then value", "scalar", required=True),
            GeneratorFieldSpec("else_value", "Else value", "scalar", required=True),
        ),
    ),
    "time_offset": GeneratorFormSpec(
        generator_id="time_offset",
        description="Date/datetime offset from a base column.",
        fields=(
            GeneratorFieldSpec(
                "base_column",
                "Base column",
                "column",
                required=True,
                dependency_source=True,
            ),
            GeneratorFieldSpec(
                "direction",
                "Direction",
                "combo",
                options=("after", "before"),
            ),
            GeneratorFieldSpec(
                "min_days",
                "Min days",
                "int",
                show_for_dtypes=("date",),
            ),
            GeneratorFieldSpec(
                "max_days",
                "Max days",
                "int",
                show_for_dtypes=("date",),
            ),
            GeneratorFieldSpec(
                "min_seconds",
                "Min seconds",
                "int",
                show_for_dtypes=("datetime",),
            ),
            GeneratorFieldSpec(
                "max_seconds",
                "Max seconds",
                "int",
                show_for_dtypes=("datetime",),
            ),
        ),
    ),
    "hierarchical_category": GeneratorFormSpec(
        generator_id="hierarchical_category",
        description="Parent-to-child category mapping.",
        fields=(
            GeneratorFieldSpec(
                "parent_column",
                "Parent column",
                "column",
                required=True,
                dependency_source=True,
            ),
            GeneratorFieldSpec(
                "hierarchy",
                "Hierarchy object",
                "json_object",
                required=True,
            ),
            GeneratorFieldSpec("default_children", "Default children", "csv_list"),
        ),
    ),
    "uniform_int": GeneratorFormSpec(
        generator_id="uniform_int",
        fields=(
            GeneratorFieldSpec("min", "Min", "int"),
            GeneratorFieldSpec("max", "Max", "int"),
        ),
    ),
    "uniform_float": GeneratorFormSpec(
        generator_id="uniform_float",
        fields=(
            GeneratorFieldSpec("min", "Min", "float"),
            GeneratorFieldSpec("max", "Max", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
        ),
    ),
    "normal": GeneratorFormSpec(
        generator_id="normal",
        fields=(
            GeneratorFieldSpec("mean", "Mean", "float"),
            GeneratorFieldSpec("stdev", "Std dev", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
            GeneratorFieldSpec("min", "Clamp min", "float"),
            GeneratorFieldSpec("max", "Clamp max", "float"),
        ),
    ),
    "lognormal": GeneratorFormSpec(
        generator_id="lognormal",
        fields=(
            GeneratorFieldSpec("median", "Median", "float"),
            GeneratorFieldSpec("sigma", "Sigma", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
            GeneratorFieldSpec("min", "Clamp min", "float"),
            GeneratorFieldSpec("max", "Clamp max", "float"),
        ),
    ),
    "choice_weighted": GeneratorFormSpec(
        generator_id="choice_weighted",
        description="Paired choice and weight lists.",
        fields=(
            GeneratorFieldSpec("choices", "Choices (comma)", "csv_list", required=True),
            GeneratorFieldSpec("weights", "Weights (comma)", "float_list"),
        ),
    ),
    "ordered_choice": GeneratorFormSpec(
        generator_id="ordered_choice",
        description="Order-path progression with weighted movement.",
        fields=(
            GeneratorFieldSpec("orders", "Orders object", "json_object", required=True),
            GeneratorFieldSpec("order_weights", "Order weights object", "json_object"),
            GeneratorFieldSpec("move_weights", "Move weights (comma)", "float_list"),
            GeneratorFieldSpec("start_index", "Start index", "int"),
        ),
    ),
    "state_transition": GeneratorFormSpec(
        generator_id="state_transition",
        description="Per-entity Markov-style state progression with dwell controls.",
        fields=(
            GeneratorFieldSpec(
                "entity_column",
                "Entity column",
                "column",
                required=True,
                dependency_source=True,
            ),
            GeneratorFieldSpec("states", "States (comma)", "csv_list", required=True),
            GeneratorFieldSpec("start_state", "Start state", "scalar"),
            GeneratorFieldSpec("start_weights", "Start weights object", "json_object"),
            GeneratorFieldSpec("transitions", "Transitions object", "json_object", required=True),
            GeneratorFieldSpec("terminal_states", "Terminal states (comma)", "csv_list"),
            GeneratorFieldSpec("dwell_min", "Dwell min", "int"),
            GeneratorFieldSpec("dwell_max", "Dwell max", "int"),
            GeneratorFieldSpec("dwell_by_state", "Dwell-by-state object", "json_object"),
        ),
    ),
    "date": GeneratorFormSpec(
        generator_id="date",
        fields=(
            GeneratorFieldSpec("start", "Start date", "text"),
            GeneratorFieldSpec("end", "End date", "text"),
        ),
    ),
    "timestamp_utc": GeneratorFormSpec(
        generator_id="timestamp_utc",
        fields=(
            GeneratorFieldSpec("start", "Start datetime", "text"),
            GeneratorFieldSpec("end", "End datetime", "text"),
        ),
    ),
    "latitude": GeneratorFormSpec(
        generator_id="latitude",
        fields=(
            GeneratorFieldSpec("min", "Min", "float"),
            GeneratorFieldSpec("max", "Max", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
        ),
    ),
    "longitude": GeneratorFormSpec(
        generator_id="longitude",
        fields=(
            GeneratorFieldSpec("min", "Min", "float"),
            GeneratorFieldSpec("max", "Max", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
        ),
    ),
    "money": GeneratorFormSpec(
        generator_id="money",
        fields=(
            GeneratorFieldSpec("min", "Min", "float"),
            GeneratorFieldSpec("max", "Max", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
        ),
    ),
    "percent": GeneratorFormSpec(
        generator_id="percent",
        fields=(
            GeneratorFieldSpec("min", "Min", "float"),
            GeneratorFieldSpec("max", "Max", "float"),
            GeneratorFieldSpec("decimals", "Decimals", "int"),
        ),
    ),
}


def get_generator_form_spec(generator_id: str) -> GeneratorFormSpec | None:
    return GENERATOR_FORM_SPECS.get(generator_id.strip())


def visible_fields_for(
    generator_id: str,
    *,
    dtype: str,
    include_cross_cutting: bool = True,
) -> list[GeneratorFieldSpec]:
    fields: list[GeneratorFieldSpec] = []
    spec = get_generator_form_spec(generator_id)
    if spec is not None:
        for field_spec in spec.fields:
            if field_spec.is_visible_for_dtype(dtype):
                fields.append(field_spec)
    if include_cross_cutting:
        for field_spec in CROSS_CUTTING_FIELDS:
            if field_spec.is_visible_for_dtype(dtype):
                fields.append(field_spec)
    return fields


def known_param_keys_for(generator_id: str, *, dtype: str) -> set[str]:
    return {field_spec.field_id for field_spec in visible_fields_for(generator_id, dtype=dtype)}


def split_form_state(
    generator_id: str,
    *,
    dtype: str,
    params: dict[str, object] | None,
) -> GeneratorFormState:
    payload = params or {}
    known_keys = known_param_keys_for(generator_id, dtype=dtype)
    known: dict[str, object] = {}
    passthrough: dict[str, object] = {}
    for key, value in payload.items():
        if key in known_keys:
            known[key] = value
        else:
            passthrough[key] = value
    return GeneratorFormState(known_params=known, passthrough_params=passthrough, validation_errors=())


def missing_form_specs_for_generators(generators: list[str]) -> list[str]:
    missing: list[str] = []
    for generator in generators:
        key = generator.strip()
        if key == "":
            continue
        if key not in GENERATOR_FORM_SPECS:
            missing.append(key)
    return sorted(set(missing))


def parse_scalar_text(raw: str) -> object:
    text = raw.strip()
    if text == "":
        raise ValueError("value is required")
    try:
        return json.loads(text)
    except Exception:
        return text


def parse_field_text(field_spec: GeneratorFieldSpec, raw: str) -> object | None:
    text = raw.strip()
    if text == "":
        return None

    kind = field_spec.control_kind
    if kind in {"text", "combo", "column", "path"}:
        return text
    if kind == "int":
        try:
            return int(text)
        except (TypeError, ValueError) as exc:
            raise ValueError("must be an integer") from exc
    if kind == "float":
        try:
            return float(text)
        except (TypeError, ValueError) as exc:
            raise ValueError("must be numeric") from exc
    if kind == "scalar":
        return parse_scalar_text(text)
    if kind == "csv_list":
        tokens = [part.strip() for part in text.split(",") if part.strip() != ""]
        if len(tokens) == 0:
            return []
        parsed: list[object] = []
        for token in tokens:
            parsed.append(parse_scalar_text(token))
        return parsed
    if kind == "float_list":
        tokens = [part.strip() for part in text.split(",") if part.strip() != ""]
        parsed: list[float] = []
        for token in tokens:
            try:
                parsed.append(float(token))
            except (TypeError, ValueError) as exc:
                raise ValueError("must be a comma-separated numeric list") from exc
        return parsed
    if kind == "json_object":
        try:
            value = json.loads(text)
        except Exception as exc:
            raise ValueError("must be valid JSON object text") from exc
        if not isinstance(value, dict):
            raise ValueError("must be a JSON object")
        return value
    raise ValueError(f"unsupported control kind '{kind}'")


def format_field_value(field_spec: GeneratorFieldSpec, value: object | None) -> str:
    if value is None:
        return ""
    kind = field_spec.control_kind
    if kind in {"text", "combo", "column", "path"}:
        return str(value)
    if kind == "int":
        return str(int(value))
    if kind == "float":
        return str(float(value))
    if kind == "scalar":
        if isinstance(value, str):
            return value
        return json.dumps(value)
    if kind == "csv_list":
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return str(value)
    if kind == "float_list":
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        return str(value)
    if kind == "json_object":
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True)
        return "{}"
    return str(value)
