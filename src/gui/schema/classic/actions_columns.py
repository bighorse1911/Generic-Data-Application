"""Compatibility hub for classic schema-screen column actions."""

from __future__ import annotations

from src.gui.schema.classic.actions_columns_editor import (
    _apply_generator_params_template,
    _clear_column_editor,
    _load_column_into_editor,
    _on_column_dtype_changed,
    _on_column_generator_changed,
    _on_column_selected,
    _on_pattern_entry_focus_out,
    _on_pattern_preset_selected,
    _on_table_correlation_groups_json_apply,
    _open_table_correlation_groups_editor,
    _refresh_columns_tree,
    _refresh_generator_options_for_dtype,
    _selected_column_index,
    _sync_pattern_preset_from_pattern,
)
from src.gui.schema.classic.actions_columns_mutations import (
    _add_column,
    _apply_selected_column_changes,
    _move_selected_column,
    _remove_selected_column,
)
from src.gui.schema.classic.actions_columns_spec import (
    _column_spec_from_editor,
    _int_columns,
    _parse_column_name_csv,
    _parse_optional_column_name,
    _table_pk_name,
)

__all__ = [
    "_refresh_columns_tree",
    "_selected_column_index",
    "_clear_column_editor",
    "_load_column_into_editor",
    "_on_column_dtype_changed",
    "_on_column_generator_changed",
    "_refresh_generator_options_for_dtype",
    "_on_pattern_entry_focus_out",
    "_on_pattern_preset_selected",
    "_sync_pattern_preset_from_pattern",
    "_apply_generator_params_template",
    "_open_table_correlation_groups_editor",
    "_on_table_correlation_groups_json_apply",
    "_on_column_selected",
    "_column_spec_from_editor",
    "_parse_column_name_csv",
    "_parse_optional_column_name",
    "_table_pk_name",
    "_int_columns",
    "_add_column",
    "_apply_selected_column_changes",
    "_remove_selected_column",
    "_move_selected_column",
]

