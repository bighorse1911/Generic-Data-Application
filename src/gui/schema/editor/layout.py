"""Compatibility hub for schema-editor layout concerns."""

from __future__ import annotations

from src.gui.schema.editor.layout_build import _build, build_header, build_status_bar, on_hide, on_show
from src.gui.schema.editor.layout_modes import (
    _apply_schema_design_mode_ui,
    _collect_hidden_mode_value_labels,
    _current_schema_design_mode,
    _mode_allowed_generators_for_dtype,
    _on_schema_design_mode_changed,
    _project_has_advanced_values,
    _project_has_out_of_mode_generators,
    _set_grid_group_visible,
    _set_schema_design_mode,
    _table_has_complex_values,
    _table_has_medium_values,
)
from src.gui.schema.editor.layout_navigation import _on_back_requested, _on_main_tab_changed, _on_screen_destroy
from src.gui.schema.editor.layout_onboarding import _refresh_onboarding_hints
from src.gui.schema.editor.layout_panels import (
    build_columns_panel,
    build_generate_panel,
    build_project_panel,
    build_relationships_panel,
    build_tables_panel,
)
from src.gui.schema.editor.layout_shortcuts import _register_focus_anchors, _register_shortcuts

__all__ = [
    "_build",
    "on_show",
    "on_hide",
    "build_header",
    "_current_schema_design_mode",
    "_set_schema_design_mode",
    "_on_schema_design_mode_changed",
    "_mode_allowed_generators_for_dtype",
    "_set_grid_group_visible",
    "_project_has_advanced_values",
    "_table_has_medium_values",
    "_table_has_complex_values",
    "_project_has_out_of_mode_generators",
    "_collect_hidden_mode_value_labels",
    "_apply_schema_design_mode_ui",
    "build_project_panel",
    "build_tables_panel",
    "build_columns_panel",
    "build_relationships_panel",
    "build_generate_panel",
    "build_status_bar",
    "_on_back_requested",
    "_on_main_tab_changed",
    "_register_shortcuts",
    "_register_focus_anchors",
    "_on_screen_destroy",
    "_refresh_onboarding_hints",
]
