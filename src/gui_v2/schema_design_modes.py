"""Schema design mode policy for schema_project_v2."""

from __future__ import annotations

from typing import Literal

SchemaDesignMode = Literal["simple", "medium", "complex"]

SCHEMA_DESIGN_MODES: tuple[SchemaDesignMode, ...] = ("simple", "medium", "complex")
DEFAULT_SCHEMA_DESIGN_MODE: SchemaDesignMode = "simple"

SIMPLE_GENERATORS: tuple[str, ...] = (
    "",
    "uniform_int",
    "uniform_float",
    "normal",
    "lognormal",
    "choice_weighted",
    "date",
    "timestamp_utc",
    "latitude",
    "longitude",
    "money",
    "percent",
)

MEDIUM_GENERATORS: tuple[str, ...] = (
    *SIMPLE_GENERATORS,
    "sample_csv",
    "if_then",
    "time_offset",
    "hierarchical_category",
    "ordered_choice",
)

COMPLEX_GENERATORS: tuple[str, ...] = (
    *MEDIUM_GENERATORS,
    "derived_expr",
    "state_transition",
)

_GENERATOR_ALLOWLIST_BY_MODE: dict[SchemaDesignMode, tuple[str, ...]] = {
    "simple": SIMPLE_GENERATORS,
    "medium": MEDIUM_GENERATORS,
    "complex": COMPLEX_GENERATORS,
}


def normalize_schema_design_mode(raw: object) -> SchemaDesignMode:
    text = str(raw).strip().lower()
    if text in SCHEMA_DESIGN_MODES:
        return text  # type: ignore[return-value]
    return DEFAULT_SCHEMA_DESIGN_MODE


def allowed_generators_for_mode(mode: object) -> tuple[str, ...]:
    normalized = normalize_schema_design_mode(mode)
    return _GENERATOR_ALLOWLIST_BY_MODE[normalized]


def is_mode_downgrade(previous: object, current: object) -> bool:
    prev = normalize_schema_design_mode(previous)
    now = normalize_schema_design_mode(current)
    rank = {"simple": 0, "medium": 1, "complex": 2}
    return rank[now] < rank[prev]

