from __future__ import annotations

from collections.abc import Callable
import csv
import json
import logging
import os
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from src.config import AppConfig
from src.derived_expression import extract_derived_expression_references
from src.generator_project import generate_project_rows
from src.gui_kit.column_chooser import ColumnChooserDialog
from src.gui_kit.error_surface import ErrorSurface, show_error_dialog, show_warning_dialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.json_editor import JsonEditorDialog
from src.gui_kit.layout import BaseScreen
from src.gui_kit.scroll import wheel_units_from_delta
from src.gui_kit.table import TableView
from src.gui_kit.table_keyboard import install_treeview_keyboard_support
from src.gui_kit.ui_dispatch import safe_dispatch
from src.gui_kit.validation import InlineValidationEntry, InlineValidationSummary
from src.schema_project_io import load_project_from_json, save_project_to_json
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec, validate_project
from src.storage_sqlite_project import create_tables, insert_project_rows

from src.gui.schema.classic import actions_columns as classic_actions_columns
from src.gui.schema.classic import actions_columns_editor as classic_actions_columns_editor
from src.gui.schema.classic import actions_columns_mutations as classic_actions_columns_mutations
from src.gui.schema.classic import actions_columns_spec as classic_actions_columns_spec
from src.gui.schema.classic import actions_fks as classic_actions_fks
from src.gui.schema.classic import actions_generation as classic_actions_generation
from src.gui.schema.classic import actions_tables as classic_actions_tables
from src.gui.schema.classic import constants as classic_constants
from src.gui.schema.classic import layout as classic_layout
from src.gui.schema.classic import layout_build as classic_layout_build
from src.gui.schema.classic import layout_init as classic_layout_init
from src.gui.schema.classic import layout_navigation as classic_layout_navigation
from src.gui.schema.classic import layout_table_selection as classic_layout_table_selection
from src.gui.schema.classic import preview as classic_preview
from src.gui.schema.classic import project_io as classic_project_io
from src.gui.schema.classic import state_dirty as classic_state_dirty
from src.gui.schema.classic import validation as classic_validation
from src.gui.schema.classic import widgets as classic_widgets

logger = logging.getLogger("gui_schema_project")

DTYPES = classic_constants.DTYPES
GENERATORS = classic_constants.GENERATORS
GENERATOR_VALID_DTYPES = classic_constants.GENERATOR_VALID_DTYPES
PATTERN_PRESET_CUSTOM = classic_constants.PATTERN_PRESET_CUSTOM
PATTERN_PRESETS = classic_constants.PATTERN_PRESETS
SCD_MODES = classic_constants.SCD_MODES
EXPORT_OPTION_CSV = classic_constants.EXPORT_OPTION_CSV
EXPORT_OPTION_SQLITE = classic_constants.EXPORT_OPTION_SQLITE
EXPORT_OPTIONS = classic_constants.EXPORT_OPTIONS

valid_generators_for_dtype = classic_constants.valid_generators_for_dtype
default_generator_params_template = classic_constants.default_generator_params_template
validate_export_option = classic_constants.validate_export_option
_gui_error = classic_constants._gui_error
_csv_export_value = classic_constants._csv_export_value

ScrollableFrame = classic_widgets.ScrollableFrame
CollapsibleSection = classic_widgets.CollapsibleSection
ValidationIssue = classic_widgets.ValidationIssue
ValidationHeatmap = classic_widgets.ValidationHeatmap


def _bind_classic_module_context(module) -> None:
    for name, value in globals().items():
        if name.startswith("__"):
            continue
        module.__dict__.setdefault(name, value)


class SchemaProjectDesignerScreen(ttk.Frame):
    """
    Schema Project Designer (Phase 1 + Phase 2):
    - Manage tables in a project
    - Edit selected table (name + row_count)
    - Edit selected table columns (add/remove/move, set PK)
    - Define FK relationships (parent->child) with cardinality min/max children and optional DG08 child-count distribution profile
    - Save/load full project JSON
    """

    ERROR_SURFACE_CONTEXT = "Schema project"
    ERROR_DIALOG_TITLE = "Schema project error"
    WARNING_DIALOG_TITLE = "Schema project warning"
    def __init__(self, parent: tk.Widget, app: 'object', cfg: AppConfig) -> None:
        return classic_layout.__init__(self, parent, app, cfg)

    def _build(self) -> None:
        return classic_layout._build(self)

    def _on_back_requested(self) -> None:
        return classic_layout._on_back_requested(self)

    def _mark_dirty(self, reason: str | None=None) -> None:
        return classic_state_dirty._mark_dirty(self, reason)

    def _mark_clean(self) -> None:
        return classic_state_dirty._mark_clean(self)

    def _on_project_meta_changed(self, *_args) -> None:
        return classic_state_dirty._on_project_meta_changed(self, *_args)

    def _mark_dirty_if_project_changed(self, before_project: SchemaProject, *, reason: str) -> None:
        return classic_state_dirty._mark_dirty_if_project_changed(self, before_project, reason=reason)

    def _confirm_discard_or_save(self, action_name: str) -> bool:
        return classic_state_dirty._confirm_discard_or_save(self, action_name)

    def _refresh_inline_validation_summary(self, issues: list[ValidationIssue]) -> None:
        return classic_validation._refresh_inline_validation_summary(self, issues)

    def _jump_to_validation_issue(self, entry: InlineValidationEntry) -> None:
        return classic_validation._jump_to_validation_issue(self, entry)

    def _jump_to_table_or_column_issue(self, table_name: str | None, column_name: str | None) -> None:
        return classic_validation._jump_to_table_or_column_issue(self, table_name, column_name)

    def _jump_to_fk_issue(self, child_table: str | None, child_column: str | None) -> None:
        return classic_validation._jump_to_fk_issue(self, child_table, child_column)

    def _preview_columns_for_table(self, table_name: str) -> list[str]:
        return classic_preview._preview_columns_for_table(self, table_name)

    def _refresh_preview_projection(self) -> None:
        return classic_preview._refresh_preview_projection(self)

    def _on_preview_paging_toggled(self) -> None:
        return classic_preview._on_preview_paging_toggled(self)

    def _on_preview_page_size_changed(self, _event=None) -> None:
        return classic_preview._on_preview_page_size_changed(self, _event)

    def _open_preview_column_chooser(self) -> None:
        return classic_preview._open_preview_column_chooser(self)

    def _on_preview_columns_applied(self, table_name: str, selected_columns: list[str]) -> None:
        return classic_preview._on_preview_columns_applied(self, table_name, selected_columns)

    def _show_error_dialog(self, location: str, message: object) -> str:
        return classic_state_dirty._show_error_dialog(self, location, message)

    def _show_warning_dialog(self, location: str, message: object) -> str:
        return classic_state_dirty._show_warning_dialog(self, location, message)

    def _notify(self, message: str, *, level: str='info', duration_ms: int | None=None) -> None:
        return classic_state_dirty._notify(self, message, level=level, duration_ms=duration_ms)

    def _show_notifications_history(self) -> None:
        return classic_state_dirty._show_notifications_history(self)

    def _on_validation_heatmap_info(self, title: str, message: str) -> None:
        return classic_validation._on_validation_heatmap_info(self, title, message)

    def _set_table_editor_enabled(self, enabled: bool) -> None:
        return classic_layout._set_table_editor_enabled(self, enabled)

    def _refresh_tables_list(self) -> None:
        return classic_layout._refresh_tables_list(self)

    def _refresh_columns_tree(self) -> None:
        return classic_actions_columns._refresh_columns_tree(self)

    def _selected_column_index(self) -> int | None:
        return classic_actions_columns._selected_column_index(self)

    def _clear_column_editor(self) -> None:
        return classic_actions_columns._clear_column_editor(self)

    def _load_column_into_editor(self, col: ColumnSpec) -> None:
        return classic_actions_columns._load_column_into_editor(self, col)

    def _on_column_dtype_changed(self, *_args) -> None:
        return classic_actions_columns._on_column_dtype_changed(self, *_args)

    def _on_column_generator_changed(self, *_args) -> None:
        return classic_actions_columns._on_column_generator_changed(self, *_args)

    def _refresh_generator_options_for_dtype(self) -> None:
        return classic_actions_columns._refresh_generator_options_for_dtype(self)

    def _on_pattern_entry_focus_out(self, _event=None) -> None:
        return classic_actions_columns._on_pattern_entry_focus_out(self, _event)

    def _on_pattern_preset_selected(self, _event=None) -> None:
        return classic_actions_columns._on_pattern_preset_selected(self, _event)

    def _sync_pattern_preset_from_pattern(self) -> None:
        return classic_actions_columns._sync_pattern_preset_from_pattern(self)

    def _apply_generator_params_template(self) -> None:
        return classic_actions_columns._apply_generator_params_template(self)

    def _open_table_correlation_groups_editor(self) -> None:
        return classic_actions_columns._open_table_correlation_groups_editor(self)

    def _on_table_correlation_groups_json_apply(self, pretty_json: str) -> None:
        return classic_actions_columns._on_table_correlation_groups_json_apply(self, pretty_json)

    def _open_project_timeline_constraints_editor(self) -> None:
        return classic_project_io._open_project_timeline_constraints_editor(self)

    def _on_project_timeline_constraints_json_apply(self, pretty_json: str) -> None:
        return classic_project_io._on_project_timeline_constraints_json_apply(self, pretty_json)

    def _open_project_data_quality_profiles_editor(self) -> None:
        return classic_project_io._open_project_data_quality_profiles_editor(self)

    def _on_project_data_quality_profiles_json_apply(self, pretty_json: str) -> None:
        return classic_project_io._on_project_data_quality_profiles_json_apply(self, pretty_json)

    def _open_project_sample_profile_fits_editor(self) -> None:
        return classic_project_io._open_project_sample_profile_fits_editor(self)

    def _on_project_sample_profile_fits_json_apply(self, pretty_json: str) -> None:
        return classic_project_io._on_project_sample_profile_fits_json_apply(self, pretty_json)

    def _open_project_locale_identity_bundles_editor(self) -> None:
        return classic_project_io._open_project_locale_identity_bundles_editor(self)

    def _on_project_locale_identity_bundles_json_apply(self, pretty_json: str) -> None:
        return classic_project_io._on_project_locale_identity_bundles_json_apply(self, pretty_json)

    def _on_column_selected(self, _event=None) -> None:
        return classic_actions_columns._on_column_selected(self, _event)

    def _column_spec_from_editor(self, *, action_prefix: str) -> ColumnSpec:
        return classic_actions_columns._column_spec_from_editor(self, action_prefix=action_prefix)

    def _parse_column_name_csv(self, raw_value: str, *, location: str, field_name: str) -> list[str] | None:
        return classic_actions_columns._parse_column_name_csv(self, raw_value, location=location, field_name=field_name)

    def _parse_optional_column_name(self, raw_value: str, *, location: str, field_name: str) -> str | None:
        return classic_actions_columns._parse_optional_column_name(self, raw_value, location=location, field_name=field_name)

    def _parse_table_correlation_groups(self, raw_value: str, *, location: str) -> list[dict[str, object]] | None:
        return classic_project_io._parse_table_correlation_groups(self, raw_value, location=location)

    def _parse_project_timeline_constraints(self, raw_value: str, *, location: str) -> list[dict[str, object]] | None:
        return classic_project_io._parse_project_timeline_constraints(self, raw_value, location=location)

    def _parse_project_data_quality_profiles(self, raw_value: str, *, location: str) -> list[dict[str, object]] | None:
        return classic_project_io._parse_project_data_quality_profiles(self, raw_value, location=location)

    def _parse_project_sample_profile_fits(self, raw_value: str, *, location: str) -> list[dict[str, object]] | None:
        return classic_project_io._parse_project_sample_profile_fits(self, raw_value, location=location)

    def _parse_project_locale_identity_bundles(self, raw_value: str, *, location: str) -> list[dict[str, object]] | None:
        return classic_project_io._parse_project_locale_identity_bundles(self, raw_value, location=location)

    def _apply_project_vars_to_model(self) -> None:
        return classic_project_io._apply_project_vars_to_model(self)

    def _table_pk_name(self, table_name: str) -> str:
        return classic_actions_columns._table_pk_name(self, table_name)

    def _int_columns(self, table_name: str) -> list[str]:
        return classic_actions_columns._int_columns(self, table_name)

    def _refresh_fk_dropdowns(self) -> None:
        return classic_actions_fks._refresh_fk_dropdowns(self)

    def _sync_fk_defaults(self) -> None:
        return classic_actions_fks._sync_fk_defaults(self)

    def _refresh_fks_tree(self) -> None:
        return classic_actions_fks._refresh_fks_tree(self)

    def _selected_fk_index(self) -> int | None:
        return classic_actions_fks._selected_fk_index(self)

    def _add_table(self) -> None:
        return classic_actions_tables._add_table(self)

    def _find_dependency_cycle(self, columns: list[ColumnSpec]) -> list[str] | None:
        return classic_validation._find_dependency_cycle(self, columns)

    def _validate_project_detailed(self, project: SchemaProject) -> list[ValidationIssue]:
        return classic_validation._validate_project_detailed(self, project)

    def _run_validation(self) -> None:
        return classic_validation._run_validation(self)

    def _on_generate_project(self) -> None:
        return classic_actions_generation._on_generate_project(self)

    def _remove_table(self) -> None:
        return classic_actions_tables._remove_table(self)

    def _on_table_selected(self, _event=None) -> None:
        return classic_layout._on_table_selected(self, _event)

    def _load_selected_table_into_editor(self) -> None:
        return classic_layout._load_selected_table_into_editor(self)

    def _apply_table_changes(self) -> None:
        return classic_actions_tables._apply_table_changes(self)

    def _add_column(self) -> None:
        return classic_actions_columns._add_column(self)

    def _apply_selected_column_changes(self) -> None:
        return classic_actions_columns._apply_selected_column_changes(self)

    def _remove_selected_column(self) -> None:
        return classic_actions_columns._remove_selected_column(self)

    def _move_selected_column(self, delta: int) -> None:
        return classic_actions_columns._move_selected_column(self, delta)

    def _add_fk(self) -> None:
        return classic_actions_fks._add_fk(self)

    def _remove_selected_fk(self) -> None:
        return classic_actions_fks._remove_selected_fk(self)

    def _browse_db_path(self) -> None:
        return classic_layout._browse_db_path(self)

    def _ui_alive(self) -> bool:
        return classic_state_dirty._ui_alive(self)

    def _post_ui_callback(self, callback) -> None:
        return classic_state_dirty._post_ui_callback(self, callback)

    def _set_running(self, running: bool, msg: str) -> None:
        return classic_actions_generation._set_running(self, running, msg)

    def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
        return classic_actions_generation._on_generated_ok(self, rows)

    def _refresh_preview(self) -> None:
        return classic_preview._refresh_preview(self)

    def _clear_preview_tree(self) -> None:
        return classic_preview._clear_preview_tree(self)

    def _render_preview_rows(self, rows: list[dict[str, object]]) -> None:
        return classic_preview._render_preview_rows(self, rows)

    def _on_export_data(self) -> None:
        return classic_actions_generation._on_export_data(self)

    def _on_export_csv(self) -> None:
        return classic_actions_generation._on_export_csv(self)

    def _on_create_insert_sqlite(self) -> None:
        return classic_actions_generation._on_create_insert_sqlite(self)

    def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
        return classic_actions_generation._on_sqlite_ok(self, db_path, counts)

    def _clear_generated(self) -> None:
        return classic_actions_generation._clear_generated(self)

    def _on_job_failed(self, msg: str) -> None:
        return classic_actions_generation._on_job_failed(self, msg)

    def _update_generate_enabled(self) -> None:
        return classic_state_dirty._update_generate_enabled(self)

    def _make_sample_project(self, n: int=10) -> SchemaProject:
        return classic_actions_generation._make_sample_project(self, n)

    def _on_generate_sample(self) -> None:
        return classic_actions_generation._on_generate_sample(self)

    def _save_project(self) -> bool:
        return classic_project_io._save_project(self)

    def _load_project(self, *, confirm_unsaved: bool=True) -> None:
        return classic_project_io._load_project(self, confirm_unsaved=confirm_unsaved)

for _classic_module in (
    classic_layout,
    classic_layout_init,
    classic_layout_build,
    classic_layout_table_selection,
    classic_layout_navigation,
    classic_state_dirty,
    classic_validation,
    classic_preview,
    classic_project_io,
    classic_actions_tables,
    classic_actions_columns,
    classic_actions_columns_editor,
    classic_actions_columns_spec,
    classic_actions_columns_mutations,
    classic_actions_fks,
    classic_actions_generation,
):
    _bind_classic_module_context(_classic_module)


__all__ = [
    "SchemaProjectDesignerScreen",
    "ScrollableFrame",
    "CollapsibleSection",
    "ValidationIssue",
    "ValidationHeatmap",
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
    "filedialog",
    "messagebox",
    "save_project_to_json",
    "load_project_from_json",
]
