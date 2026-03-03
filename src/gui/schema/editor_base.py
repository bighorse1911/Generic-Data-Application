import json
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Iterable
from pathlib import Path

from src.generator_project import generate_project_rows
from src.gui_kit.accessibility import FocusController
from src.gui_kit.column_chooser import ColumnChooserDialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.forms import FormBuilder
from src.gui_kit.job_lifecycle import JobLifecycleController
from src.gui_kit.json_editor import JsonEditorDialog
from src.gui_kit.layout import BaseScreen
from src.gui_kit.preferences import WorkspacePreferencesStore
from src.gui_kit.undo import SnapshotCommand, UndoStack
from src.gui_kit.panels import CollapsiblePanel, Tabs
from src.gui_kit.search import SearchEntry
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.scroll import ScrollFrame
from src.gui_kit.table import TableView
from src.gui_kit.tokens import TokenEntry
from src.gui_kit.validation import InlineValidationEntry, InlineValidationSummary
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec, validate_project
from src.gui_schema_core import SchemaProjectDesignerScreen
from src.gui_schema_shared import (
    DTYPES,
    EXPORT_OPTIONS,
    GENERATORS,
    PATTERN_PRESETS,
    SCD_MODES,
    ValidationIssue,
    ValidationHeatmap,
    valid_generators_for_dtype,
)
from src.schema_project_io import load_project_from_json, save_project_to_json
from src.storage_sqlite_project import create_tables, insert_project_rows
from src.gui_v2.schema_design_modes import (
    DEFAULT_SCHEMA_DESIGN_MODE,
    SchemaDesignMode,
    allowed_generators_for_mode,
    is_mode_downgrade,
    normalize_schema_design_mode,
)

from src.gui.schema.editor import actions_columns as editor_actions_columns
from src.gui.schema.editor import actions_fks as editor_actions_fks
from src.gui.schema.editor import actions_generation as editor_actions_generation
from src.gui.schema.editor import actions_tables as editor_actions_tables
from src.gui.schema.editor.base_types import (
    EditorUndoSnapshot,
    FILTER_PAGE_SIZE,
    IndexedFilterRow,
    STARTER_FIXTURE_PATH,
    UNDO_STACK_LIMIT,
    VALIDATION_DEBOUNCE_MS,
)
from src.gui.schema.editor.context_binding import bind_editor_modules_from_scope
from src.gui.schema.editor import filters as editor_filters
from src.gui.schema.editor import jobs as editor_jobs
from src.gui.schema.editor import layout as editor_layout
from src.gui.schema.editor import layout_build as editor_layout_build
from src.gui.schema.editor import layout_modes as editor_layout_modes
from src.gui.schema.editor import layout_navigation as editor_layout_navigation
from src.gui.schema.editor import layout_onboarding as editor_layout_onboarding
from src.gui.schema.editor import layout_panels as editor_layout_panels
from src.gui.schema.editor import layout_panels_columns as editor_layout_panels_columns
from src.gui.schema.editor import layout_panels_generate as editor_layout_panels_generate
from src.gui.schema.editor import layout_panels_project as editor_layout_panels_project
from src.gui.schema.editor import layout_panels_relationships as editor_layout_panels_relationships
from src.gui.schema.editor import layout_panels_tables as editor_layout_panels_tables
from src.gui.schema.editor import layout_shortcuts as editor_layout_shortcuts
from src.gui.schema.editor import preview as editor_preview
from src.gui.schema.editor import project_io as editor_project_io
from src.gui.schema.editor import state_undo as editor_state_undo
from src.gui.schema.editor import validation as editor_validation


class SchemaEditorBaseScreen(SchemaProjectDesignerScreen, BaseScreen):
    """
    Layout-only refactor of SchemaProjectDesignerScreen using reusable gui_kit
    components. Business logic and callbacks are inherited unchanged.
    """

    WORKSPACE_STATE_ROUTE_KEY = "schema_project_v2"

    def _build(self) -> None:
        return editor_layout._build(self)


    def on_show(self) -> None:
        return editor_layout.on_show(self)


    def on_hide(self) -> None:
        return editor_layout.on_hide(self)


    def _run_job_async(self, worker, on_done, on_failed) -> None:
        return editor_jobs._run_job_async(self, worker, on_done, on_failed)


    def build_header(self) -> ttk.Frame:
        return editor_layout.build_header(self)


    def _current_schema_design_mode(self) -> SchemaDesignMode:
        return editor_layout._current_schema_design_mode(self)


    def _set_schema_design_mode(self, mode: object, *, emit_feedback: bool, persist: bool) -> None:
        return editor_layout._set_schema_design_mode(self, mode, emit_feedback=emit_feedback, persist=persist)


    def _on_schema_design_mode_changed(self, *_args) -> None:
        return editor_layout._on_schema_design_mode_changed(self, *_args)


    def _mode_allowed_generators_for_dtype(self, dtype: str) -> list[str]:
        return editor_layout._mode_allowed_generators_for_dtype(self, dtype)


    @staticmethod
    def _set_grid_group_visible(widget: object, visible: bool) -> None:
        return editor_layout._set_grid_group_visible(widget, visible)


    def _project_has_advanced_values(self) -> bool:
        return editor_layout._project_has_advanced_values(self)


    @staticmethod
    def _table_has_medium_values(table: TableSpec) -> bool:
        return editor_layout._table_has_medium_values(table)


    @staticmethod
    def _table_has_complex_values(table: TableSpec) -> bool:
        return editor_layout._table_has_complex_values(table)


    def _project_has_out_of_mode_generators(self, mode: SchemaDesignMode) -> bool:
        return editor_layout._project_has_out_of_mode_generators(self, mode)


    def _collect_hidden_mode_value_labels(self, mode: SchemaDesignMode) -> list[str]:
        return editor_layout._collect_hidden_mode_value_labels(self, mode)


    def _apply_schema_design_mode_ui(self, *, emit_feedback: bool, persist: bool) -> None:
        return editor_layout._apply_schema_design_mode_ui(self, emit_feedback=emit_feedback, persist=persist)


    def build_project_panel(self) -> CollapsiblePanel:
        return editor_layout.build_project_panel(self)


    def build_tables_panel(self) -> CollapsiblePanel:
        return editor_layout.build_tables_panel(self)


    def build_columns_panel(self) -> CollapsiblePanel:
        return editor_layout.build_columns_panel(self)


    def build_relationships_panel(self) -> CollapsiblePanel:
        return editor_layout.build_relationships_panel(self)


    def build_generate_panel(self) -> CollapsiblePanel:
        return editor_layout.build_generate_panel(self)


    def build_status_bar(self) -> ttk.Frame:
        return editor_layout.build_status_bar(self)


    def _on_back_requested(self) -> None:
        return editor_layout._on_back_requested(self)


    def _refresh_inline_validation_summary(self, issues: list[ValidationIssue] | None=None) -> None:
        return editor_validation._refresh_inline_validation_summary(self, issues)


    def _jump_to_validation_issue(self, entry: InlineValidationEntry) -> None:
        return editor_validation._jump_to_validation_issue(self, entry)


    def _jump_to_table_or_column_issue(self, table_name: str | None, column_name: str | None) -> None:
        return editor_validation._jump_to_table_or_column_issue(self, table_name, column_name)


    def _jump_to_fk_issue(self, child_table: str | None, child_column: str | None) -> None:
        return editor_validation._jump_to_fk_issue(self, child_table, child_column)


    def _preview_columns_for_table(self, table_name: str) -> list[str]:
        return editor_preview._preview_columns_for_table(self, table_name)


    def _refresh_preview_projection(self) -> None:
        return editor_preview._refresh_preview_projection(self)


    def _on_preview_page_size_changed(self, _event=None) -> None:
        return editor_preview._on_preview_page_size_changed(self, _event)


    def _open_preview_column_chooser(self) -> None:
        return editor_preview._open_preview_column_chooser(self)


    def _on_preview_columns_applied(self, table_name: str, selected_columns: list[str]) -> None:
        return editor_preview._on_preview_columns_applied(self, table_name, selected_columns)


    def _mark_dirty_if_project_changed(self, before_project, *, reason: str) -> None:
        return editor_state_undo._mark_dirty_if_project_changed(self, before_project, reason=reason)


    def _workspace_store(self) -> WorkspacePreferencesStore | None:
        return editor_state_undo._workspace_store(self)


    def _workspace_panel_state(self) -> dict[str, bool]:
        return editor_state_undo._workspace_panel_state(self)


    def _workspace_preview_column_state(self) -> dict[str, list[str]]:
        return editor_state_undo._workspace_preview_column_state(self)


    def _workspace_state_payload(self) -> dict[str, object]:
        return editor_state_undo._workspace_state_payload(self)


    def _persist_workspace_state(self) -> None:
        return editor_state_undo._persist_workspace_state(self)


    def _restore_workspace_state(self) -> None:
        return editor_state_undo._restore_workspace_state(self)


    def _on_main_tab_changed(self, _event=None) -> None:
        return editor_layout._on_main_tab_changed(self, _event)


    def _capture_undo_snapshot(self) -> EditorUndoSnapshot:
        return editor_state_undo._capture_undo_snapshot(self)


    def _apply_undo_snapshot(self, snapshot: EditorUndoSnapshot) -> None:
        return editor_state_undo._apply_undo_snapshot(self, snapshot)


    def _record_undo_snapshot(self, *, before: EditorUndoSnapshot, label: str, reason: str) -> None:
        return editor_state_undo._record_undo_snapshot(self, before=before, label=label, reason=reason)


    def _sync_dirty_from_saved_baseline(self, *, default_reason: str) -> None:
        return editor_state_undo._sync_dirty_from_saved_baseline(self, default_reason=default_reason)


    def _mark_saved_baseline(self) -> None:
        return editor_state_undo._mark_saved_baseline(self)


    def _reset_undo_history(self) -> None:
        return editor_state_undo._reset_undo_history(self)


    def _undo_blocker_reason(self) -> str | None:
        return editor_state_undo._undo_blocker_reason(self)


    def _update_undo_redo_controls(self) -> None:
        return editor_state_undo._update_undo_redo_controls(self)


    def _undo_last_change(self) -> None:
        return editor_state_undo._undo_last_change(self)


    def _redo_last_change(self) -> None:
        return editor_state_undo._redo_last_change(self)


    def _on_project_meta_changed(self, *_args) -> None:
        return editor_state_undo._on_project_meta_changed(self, *_args)


    def _register_shortcuts(self) -> None:
        return editor_layout._register_shortcuts(self)


    def _register_focus_anchors(self) -> None:
        return editor_layout._register_focus_anchors(self)


    def _on_screen_destroy(self, event) -> None:
        return editor_layout._on_screen_destroy(self, event)


    @staticmethod
    def _starter_fixture_abspath() -> Path:
        return editor_project_io._starter_fixture_abspath()


    @staticmethod
    def _build_starter_project(seed: int) -> SchemaProject:
        return editor_project_io._build_starter_project(seed)


    def _create_starter_schema(self) -> None:
        return editor_project_io._create_starter_schema(self)


    def _load_starter_fixture_shortcut(self) -> None:
        return editor_project_io._load_starter_fixture_shortcut(self)


    def _refresh_onboarding_hints(self) -> None:
        return editor_layout._refresh_onboarding_hints(self)


    def _cancel_validation_debounce(self) -> None:
        return editor_validation._cancel_validation_debounce(self)


    def _stage_incremental_validation(self, *, table_names: Iterable[str]) -> None:
        return editor_validation._stage_incremental_validation(self, table_names=table_names)


    def _stage_full_validation(self) -> None:
        return editor_validation._stage_full_validation(self)


    def _run_validation_full(self) -> None:
        return editor_validation._run_validation_full(self)


    def _run_validation(self, *, mode: str='auto') -> None:
        return editor_validation._run_validation(self, mode=mode)


    def _schedule_incremental_validation(self, table_names: set[str]) -> None:
        return editor_validation._schedule_incremental_validation(self, table_names)


    def _flush_incremental_validation(self) -> None:
        return editor_validation._flush_incremental_validation(self)


    def _execute_full_validation(self) -> None:
        return editor_validation._execute_full_validation(self)


    def _execute_incremental_validation(self, touched_tables: set[str]) -> None:
        return editor_validation._execute_incremental_validation(self, touched_tables)


    def _expand_incremental_scope_tables(self, touched_tables: set[str]) -> set[str]:
        return editor_validation._expand_incremental_scope_tables(self, touched_tables)


    def _build_validation_projection(self, table_names: set[str]) -> SchemaProject:
        return editor_validation._build_validation_projection(self, table_names)


    @staticmethod
    def _group_issues_by_table(issues: list[ValidationIssue]) -> dict[str, list[ValidationIssue]]:
        return editor_validation._group_issues_by_table(issues)


    def _rebuild_validation_cache(self, issues: list[ValidationIssue]) -> None:
        return editor_validation._rebuild_validation_cache(self, issues)


    def _merge_validation_cache(self) -> list[ValidationIssue]:
        return editor_validation._merge_validation_cache(self)


    def _apply_validation_issues(self, issues: list[ValidationIssue]) -> None:
        return editor_validation._apply_validation_issues(self, issues)


    def _focus_table_search(self) -> None:
        return editor_filters._focus_table_search(self)


    def _focus_columns_search(self) -> None:
        return editor_filters._focus_columns_search(self)


    def _focus_fk_search(self) -> None:
        return editor_filters._focus_fk_search(self)


    def _focus_next_anchor(self) -> None:
        return editor_filters._focus_next_anchor(self)


    def _focus_previous_anchor(self) -> None:
        return editor_filters._focus_previous_anchor(self)


    def _show_shortcuts_help(self) -> None:
        return editor_filters._show_shortcuts_help(self)


    def _show_notifications_history(self) -> None:
        return editor_filters._show_notifications_history(self)


    def _show_toast(self, message: str, *, level: str='info', duration_ms: int | None=None) -> None:
        return editor_filters._show_toast(self, message, level=level, duration_ms=duration_ms)


    def _open_params_json_editor(self) -> None:
        return editor_actions_columns._open_params_json_editor(self)


    def _on_params_json_apply(self, pretty_json: str) -> None:
        return editor_actions_columns._on_params_json_apply(self, pretty_json)


    def _refresh_generator_options_for_dtype(self) -> None:
        return editor_actions_columns._refresh_generator_options_for_dtype(self)


    def _refresh_tables_list(self) -> None:
        return editor_filters._refresh_tables_list(self)


    def _on_tables_search_change(self, query: str) -> None:
        return editor_filters._on_tables_search_change(self, query)


    def _on_columns_search_change(self, query: str) -> None:
        return editor_filters._on_columns_search_change(self, query)


    def _on_fk_search_change(self, query: str) -> None:
        return editor_filters._on_fk_search_change(self, query)


    @staticmethod
    def _filter_index_rows(rows: list[IndexedFilterRow], query: str) -> list[IndexedFilterRow]:
        return editor_filters._filter_index_rows(rows, query)


    @staticmethod
    def _render_indexed_rows(tree: ttk.Treeview, rows: list[IndexedFilterRow]) -> None:
        return editor_filters._render_indexed_rows(tree, rows)


    @staticmethod
    def _page_window(total_rows: int, page_index: int, page_size: int) -> tuple[int, int, int, int]:
        return editor_filters._page_window(total_rows, page_index, page_size)


    def _render_columns_filter_page(self) -> None:
        return editor_filters._render_columns_filter_page(self)


    def _render_fk_filter_page(self) -> None:
        return editor_filters._render_fk_filter_page(self)


    def _on_columns_filter_prev_page(self) -> None:
        return editor_filters._on_columns_filter_prev_page(self)


    def _on_columns_filter_next_page(self) -> None:
        return editor_filters._on_columns_filter_next_page(self)


    def _on_fk_filter_prev_page(self) -> None:
        return editor_filters._on_fk_filter_prev_page(self)


    def _on_fk_filter_next_page(self) -> None:
        return editor_filters._on_fk_filter_next_page(self)


    def _show_column_source_index(self, source_index: int) -> None:
        return editor_filters._show_column_source_index(self, source_index)


    def _show_fk_source_index(self, source_index: int) -> None:
        return editor_filters._show_fk_source_index(self, source_index)


    def _refresh_columns_tree(self) -> None:
        return editor_filters._refresh_columns_tree(self)


    def _refresh_fks_tree(self) -> None:
        return editor_filters._refresh_fks_tree(self)


    def _on_fk_selection_changed(self, _event=None) -> None:
        return editor_filters._on_fk_selection_changed(self, _event)


    def _on_preview_table_selected(self, _event=None) -> None:
        return editor_preview._on_preview_table_selected(self, _event)


    def _refresh_preview(self) -> None:
        return editor_preview._refresh_preview(self)


    def _clear_preview_tree(self) -> None:
        return editor_preview._clear_preview_tree(self)


    def _set_table_editor_enabled(self, enabled: bool) -> None:
        return editor_actions_tables._set_table_editor_enabled(self, enabled)


    def _apply_generator_params_template(self) -> None:
        return editor_actions_columns._apply_generator_params_template(self)


    def _move_column_up(self) -> None:
        return editor_actions_columns._move_column_up(self)


    def _move_column_down(self) -> None:
        return editor_actions_columns._move_column_down(self)


    def _set_running(self, running: bool, msg: str) -> None:
        return editor_jobs._set_running(self, running, msg)


    def _set_project_io_running(self, running: bool, msg: str) -> None:
        return editor_jobs._set_project_io_running(self, running, msg)


    def _project_io_busy(self) -> bool:
        return editor_jobs._project_io_busy(self)


    def _project_io_guard(self, *, action: str) -> bool:
        return editor_jobs._project_io_guard(self, action=action)


    def _start_save_project_async(self) -> bool:
        return editor_project_io._start_save_project_async(self)


    @staticmethod
    def _save_project_async_worker(project_snapshot, path: str) -> str:
        return editor_project_io._save_project_async_worker(project_snapshot, path)


    def _on_save_project_async_done(self, payload: object) -> None:
        return editor_project_io._on_save_project_async_done(self, payload)


    def _start_load_project_async(self) -> None:
        return editor_project_io._start_load_project_async(self)


    @staticmethod
    def _load_project_async_worker(path: str) -> tuple[str, object]:
        return editor_project_io._load_project_async_worker(path)


    def _on_load_project_async_done(self, payload: object) -> None:
        return editor_project_io._on_load_project_async_done(self, payload)


    def _apply_loaded_project(self, project: object, path: str) -> None:
        return editor_project_io._apply_loaded_project(self, project, path)


    def _on_project_io_failed(self, title: str, message: str) -> None:
        return editor_jobs._on_project_io_failed(self, title, message)


    def _save_project(self) -> bool:
        return editor_project_io._save_project(self)


    def _load_project(self) -> None:
        return editor_project_io._load_project(self)


    def _add_table(self) -> None:
        return editor_actions_tables._add_table(self)


    def _remove_table(self) -> None:
        return editor_actions_tables._remove_table(self)


    def _apply_table_changes(self) -> None:
        return editor_actions_tables._apply_table_changes(self)


    def _add_column(self) -> None:
        return editor_actions_columns._add_column(self)


    def _apply_selected_column_changes(self) -> None:
        return editor_actions_columns._apply_selected_column_changes(self)


    def _remove_selected_column(self) -> None:
        return editor_actions_columns._remove_selected_column(self)


    def _move_selected_column(self, delta: int) -> None:
        return editor_actions_columns._move_selected_column(self, delta)


    def _add_fk(self) -> None:
        return editor_actions_fks._add_fk(self)


    def _remove_selected_fk(self) -> None:
        return editor_actions_fks._remove_selected_fk(self)


    def _on_generate_project(self) -> None:
        return editor_actions_generation._on_generate_project(self)


    def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
        return editor_actions_generation._on_generated_ok(self, rows)


    def _clear_generated(self) -> None:
        return editor_actions_generation._clear_generated(self)


    def _on_export_csv(self) -> None:
        return editor_actions_generation._on_export_csv(self)


    def _on_create_insert_sqlite(self) -> None:
        return editor_actions_generation._on_create_insert_sqlite(self)


    def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
        return editor_actions_generation._on_sqlite_ok(self, db_path, counts)


    def _on_generate_sample(self) -> None:
        return editor_actions_generation._on_generate_sample(self)

bind_editor_modules_from_scope(globals())

