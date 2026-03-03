from __future__ import annotations

"""Generation pipeline facade and compatibility re-exports."""

from typing import Callable

from src.generation.common import _iso_date, _iso_datetime, _parse_iso_date_value, _parse_iso_datetime_value, _runtime_error, _stable_subseed
from src.generation.correlation import _apply_table_correlation_groups, _categorical_order_lookup, _correlation_sort_key
from src.generation.dependency import _dependency_order, dependency_order
from src.generation.fk_assignment import _allocate_fk_child_counts, _build_fk_parent_weights, _compile_fk_distribution_weights, _fk_lookup_identity, _fk_parent_rows_and_ids, _fk_selection_key_candidates, _normalize_fk_child_count_distribution, _resolve_fk_parent_weight, _sample_requested_fk_extras
from src.generation.locale_identity import _apply_table_locale_identity_bundles, _build_locale_identity_payload, _compile_locale_identity_bundles, _compile_locale_selector, _format_locale_phone, _normalize_locale_identity_columns
from src.generation.pipeline_orchestrator import _cache_parent_rows, _compile_parent_cache_columns, _generate_project_rows_internal
from src.generation.profile_fit import _infer_profile_from_values, _read_csv_profile_source, _resolve_sample_profile_fits
from src.generation.quality_profiles import _apply_table_data_quality_profiles, _compile_data_quality_profiles, _default_format_error_value, _profile_clamp_probability, _profile_matches_where, _profile_rate_triggered, _profile_scalar_identity
from src.generation.scd import _apply_business_key_and_scd, _apply_scd2_history, _apply_scd2_history_presized, _business_key_is_already_unique, _business_key_value_for_row, _effective_scd_tracked_columns, _enforce_business_key_unique_count, _enforce_business_key_uniqueness, _mutate_scd_tracked_value, _normalize_scd_mode, _parse_business_key_unique_count, _table_col_map, _table_pk_col_name
from src.generation.timeline import _build_parent_lookup, _compile_timeline_constraints, _enforce_table_timeline_constraints, _parse_child_temporal_or_none
from src.generation.value_generation import _apply_numeric_post, _gen_value, _gen_value_fallback, _maybe_null, _order_columns_by_dependencies
from src.schema_project_model import SchemaProject


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
