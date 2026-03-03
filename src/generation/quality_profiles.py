"""Data-quality profile (DG06) compatibility facade."""

from __future__ import annotations

from src.generation.quality_profiles_apply import _apply_table_data_quality_profiles
from src.generation.quality_profiles_compile import _compile_data_quality_profiles
from src.generation.quality_profiles_helpers import (
    _default_format_error_value,
    _profile_clamp_probability,
    _profile_matches_where,
    _profile_rate_triggered,
    _profile_scalar_identity,
)

__all__ = [
    "_profile_rate_triggered",
    "_profile_clamp_probability",
    "_profile_scalar_identity",
    "_profile_matches_where",
    "_default_format_error_value",
    "_compile_data_quality_profiles",
    "_apply_table_data_quality_profiles",
]
