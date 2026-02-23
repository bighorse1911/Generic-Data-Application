import tkinter as tk
from tkinter import filedialog, ttk
from typing import Iterable
from dataclasses import dataclass
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
)
from src.schema_project_io import load_project_from_json, save_project_to_json
from src.storage_sqlite_project import create_tables, insert_project_rows

VALIDATION_DEBOUNCE_MS = 180
FILTER_PAGE_SIZE = 200
UNDO_STACK_LIMIT = 120
STARTER_FIXTURE_PATH = Path("tests/fixtures/default_schema_project.json")


@dataclass(frozen=True)
class IndexedFilterRow:
    source_index: int
    values: tuple[object, ...]
    search_text: str


@dataclass(frozen=True)
class EditorUndoSnapshot:
    project: SchemaProject
    selected_table_index: int | None
    selected_column_index: int | None
    selected_fk_index: int | None


class SchemaEditorBaseScreen(SchemaProjectDesignerScreen, BaseScreen):
    """
    Layout-only refactor of SchemaProjectDesignerScreen using reusable gui_kit
    components. Business logic and callbacks are inherited unchanged.
    """

    WORKSPACE_STATE_ROUTE_KEY = "schema_project_v2"

    def _build(self) -> None:
        if hasattr(self, "scroll"):
            self.scroll.destroy()

        self.scroll = ScrollFrame(self, padding=16)
        self.scroll.pack(fill="both", expand=True)
        self._root_content = self.scroll.content
        self.toast_center = ToastCenter(self)
        self.shortcut_manager = ShortcutManager(self)
        self.focus_controller = FocusController(self)
        self._preview_source_table = ""
        self._preview_source_rows: list[dict[str, object]] = []
        self._preview_column_preferences: dict[str, list[str]] = {}
        self._columns_filter_index: list[IndexedFilterRow] = []
        self._columns_filter_rows: list[IndexedFilterRow] = []
        self._columns_filter_page_index = 0
        self._fk_filter_index: list[IndexedFilterRow] = []
        self._fk_filter_rows: list[IndexedFilterRow] = []
        self._fk_filter_page_index = 0

        self.build_header()

        self.main_tabs = Tabs(self._root_content)
        self.main_tabs.pack(fill="both", expand=True)

        self.schema_tab = self.main_tabs.add_tab("Schema")
        self.generate_tab = self.main_tabs.add_tab("Generate")

        self.build_project_panel()
        self.build_tables_panel()
        self.build_columns_panel()
        self.build_relationships_panel()
        self.build_generate_panel()
        self.build_status_bar()
        self.main_tabs.bind("<<NotebookTabChanged>>", self._on_main_tab_changed, add="+")
        self._restore_workspace_state()
        self._register_focus_anchors()
        self._register_shortcuts()
        self._suspend_project_meta_dirty = False
        self.project_name_var.trace_add("write", self._on_project_meta_changed)
        self.seed_var.trace_add("write", self._on_project_meta_changed)
        self.project_timeline_constraints_var.trace_add("write", self._on_project_meta_changed)
        self.enable_dirty_state_guard(context="Schema Project Designer", on_save=self._save_project)
        self.mark_clean()
        self.job_lifecycle = JobLifecycleController(
            set_running=self._set_running,
            run_async=self._run_job_async,
        )
        self.project_io_lifecycle = JobLifecycleController(
            set_running=self._set_project_io_running,
            run_async=self._run_job_async,
        )
        self._project_io_running = False
        self.undo_stack = UndoStack(limit=UNDO_STACK_LIMIT)
        self._undo_saved_project: SchemaProject = self.project
        self._validation_cache_project_issues: list[ValidationIssue] = []
        self._validation_cache_table_issues: dict[str, list[ValidationIssue]] = {}
        self._validation_pending_mode: str = "full"
        self._validation_pending_tables: set[str] = set()
        self._validation_debounce_after_id: str | None = None
        self.bind("<Destroy>", self._on_screen_destroy, add="+")
        self._update_undo_redo_controls()
        self._refresh_onboarding_hints()

        # Keep default platform theme; dark mode is intentionally disabled.
        self.kit_dark_mode_enabled = False

    def on_show(self) -> None:
        if hasattr(self, "shortcut_manager"):
            self.shortcut_manager.activate()
        if hasattr(self, "focus_controller"):
            self.focus_controller.focus_default()
        self._refresh_onboarding_hints()

    def on_hide(self) -> None:
        self._persist_workspace_state()
        if hasattr(self, "shortcut_manager"):
            self.shortcut_manager.deactivate()

    def _run_job_async(self, worker, on_done, on_failed) -> None:
        self.safe_threaded_job(worker, on_done, on_failed)

    def build_header(self) -> ttk.Frame:
        header = BaseScreen.build_header(
            self,
            self._root_content,
            title="Schema Project Designer (Kit Preview)",
            back_command=self._on_back_requested,
        )
        ttk.Button(header, text="Notifications", command=self._show_notifications_history).pack(side="right", padx=(0, 6))
        ttk.Button(header, text="Shortcuts", command=self._show_shortcuts_help).pack(side="right")
        return header

    def build_project_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.schema_tab, "Project", collapsed=False)
        panel.pack(fill="x", pady=(0, 10))
        self.project_panel = panel

        panel.body.columnconfigure(0, weight=1)

        project_box = ttk.LabelFrame(panel.body, text="Project settings", padding=10)
        project_box.grid(row=0, column=0, sticky="ew")
        project_box.columnconfigure(0, weight=1)

        project_form_frame = ttk.Frame(project_box)
        project_form_frame.grid(row=0, column=0, sticky="ew")
        form = FormBuilder(project_form_frame)
        self.project_name_entry = form.add_entry("Project name", self.project_name_var)
        self.seed_entry = form.add_entry("Seed", self.seed_var, width=12)
        self.project_timeline_constraints_entry = form.add_entry(
            "Timeline constraints JSON (optional)",
            self.project_timeline_constraints_var,
        )

        self.project_timeline_constraints_editor_btn = ttk.Button(
            project_box,
            text="Open timeline constraints JSON editor",
            command=self._open_project_timeline_constraints_editor,
        )
        self.project_timeline_constraints_editor_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        buttons = ttk.Frame(project_box)
        buttons.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        self.save_project_btn = ttk.Button(buttons, text="Save project JSON", command=self._start_save_project_async)
        self.save_project_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.load_project_btn = ttk.Button(buttons, text="Load project JSON", command=self._start_load_project_async)
        self.load_project_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        undo_row = ttk.Frame(project_box)
        undo_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        undo_row.columnconfigure(0, weight=1)
        undo_row.columnconfigure(1, weight=1)
        self.undo_btn = ttk.Button(undo_row, text="Undo", command=self._undo_last_change)
        self.undo_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.redo_btn = ttk.Button(undo_row, text="Redo", command=self._redo_last_change)
        self.redo_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        validation_box = ttk.LabelFrame(panel.body, text="Schema validation", padding=10)
        validation_box.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        validation_box.columnconfigure(0, weight=1)
        validation_box.rowconfigure(1, weight=1)
        validation_box.rowconfigure(2, weight=0)

        validation_top = ttk.Frame(validation_box)
        validation_top.grid(row=0, column=0, sticky="ew")
        validation_top.columnconfigure(1, weight=1)

        self.run_validation_btn = ttk.Button(
            validation_top,
            text="Run validation",
            command=self._run_validation_full,
        )
        self.run_validation_btn.grid(row=0, column=0, sticky="w")
        ttk.Label(validation_top, textvariable=self.validation_summary_var).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(10, 0),
        )

        self.heatmap = ValidationHeatmap(validation_box)
        self.heatmap.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.inline_validation = InlineValidationSummary(
            validation_box,
            on_jump=self._jump_to_validation_issue,
        )
        self.inline_validation.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        quick_start_box = ttk.LabelFrame(panel.body, text="First-run quick start", padding=10)
        quick_start_box.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        quick_start_box.columnconfigure(0, weight=1)

        self.onboarding_project_hint_var = tk.StringVar(value="")
        self.onboarding_project_hint_label = ttk.Label(
            quick_start_box,
            textvariable=self.onboarding_project_hint_var,
            justify="left",
            wraplength=860,
        )
        self.onboarding_project_hint_label.grid(row=0, column=0, sticky="ew")

        quick_start_actions = ttk.Frame(quick_start_box)
        quick_start_actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        quick_start_actions.columnconfigure(0, weight=1)
        quick_start_actions.columnconfigure(1, weight=1)
        quick_start_actions.columnconfigure(2, weight=1)

        self.create_starter_schema_btn = ttk.Button(
            quick_start_actions,
            text="Create starter schema",
            command=self._create_starter_schema,
        )
        self.create_starter_schema_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.load_starter_fixture_btn = ttk.Button(
            quick_start_actions,
            text="Load starter fixture",
            command=self._load_starter_fixture_shortcut,
        )
        self.load_starter_fixture_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.open_generate_tab_btn = ttk.Button(
            quick_start_actions,
            text="Open Generate tab",
            command=lambda: self.main_tabs.select(self.generate_tab),
        )
        self.open_generate_tab_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        return panel

    def build_tables_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.schema_tab, "Tables", collapsed=False)
        panel.pack(fill="both", expand=True, pady=(0, 10))
        self.tables_panel = panel

        panel.body.columnconfigure(0, weight=1)
        panel.body.columnconfigure(1, weight=2)
        panel.body.rowconfigure(0, weight=1)

        left_box = ttk.LabelFrame(panel.body, text="Tables", padding=8)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_box.columnconfigure(0, weight=1)
        left_box.rowconfigure(1, weight=1)

        self.tables_search = SearchEntry(left_box, on_change=self._on_tables_search_change, delay_ms=150)
        self.tables_search.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        list_frame = ttk.Frame(left_box)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tables_list = tk.Listbox(list_frame, height=10, exportselection=False)
        self.tables_list.grid(row=0, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tables_list.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        self.tables_list.configure(yscrollcommand=table_scroll.set)
        self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

        table_buttons = ttk.Frame(left_box)
        table_buttons.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        table_buttons.columnconfigure(0, weight=1)
        table_buttons.columnconfigure(1, weight=1)
        ttk.Button(table_buttons, text="+ Add table", command=self._add_table).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(table_buttons, text="Remove selected", command=self._remove_table).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(4, 0),
        )

        self.tables_empty_hint_var = tk.StringVar(value="")
        self.tables_empty_hint_label = ttk.Label(
            left_box,
            textvariable=self.tables_empty_hint_var,
            justify="left",
            wraplength=340,
        )
        self.tables_empty_hint_label.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        right_box = ttk.LabelFrame(panel.body, text="Selected table", padding=8)
        right_box.grid(row=0, column=1, sticky="nsew")
        right_box.columnconfigure(0, weight=1)

        table_form_frame = ttk.Frame(right_box)
        table_form_frame.grid(row=0, column=0, sticky="ew")
        table_form = FormBuilder(table_form_frame)
        self.table_name_entry = table_form.add_entry("Table name", self.table_name_var)
        self.row_count_entry = table_form.add_entry("Root row count", self.row_count_var, width=12)
        self.table_business_key_unique_count_entry = table_form.add_entry(
            "Unique business keys (optional)",
            self.table_business_key_unique_count_var,
            width=12,
        )
        self.table_business_key_entry = TokenEntry(table_form_frame, textvariable=self.table_business_key_var)
        table_form.add_widget("Business key columns (comma)", self.table_business_key_entry)
        self.table_business_key_static_entry = TokenEntry(
            table_form_frame,
            textvariable=self.table_business_key_static_columns_var,
        )
        table_form.add_widget("Business key static columns (comma)", self.table_business_key_static_entry)
        self.table_business_key_changing_entry = TokenEntry(
            table_form_frame,
            textvariable=self.table_business_key_changing_columns_var,
        )
        table_form.add_widget("Business key changing columns (comma)", self.table_business_key_changing_entry)
        self.table_scd_mode_combo = table_form.add_combo(
            "SCD mode",
            self.table_scd_mode_var,
            SCD_MODES,
            readonly=True,
        )
        self.table_scd_tracked_entry = TokenEntry(table_form_frame, textvariable=self.table_scd_tracked_columns_var)
        table_form.add_widget("SCD tracked columns (comma)", self.table_scd_tracked_entry)
        self.table_scd_active_from_entry = table_form.add_entry(
            "SCD active from column",
            self.table_scd_active_from_var,
        )
        self.table_scd_active_to_entry = table_form.add_entry(
            "SCD active to column",
            self.table_scd_active_to_var,
        )
        self.table_correlation_groups_entry = table_form.add_entry(
            "Correlation groups JSON (optional)",
            self.table_correlation_groups_var,
        )
        self.table_correlation_groups_editor_btn = ttk.Button(
            right_box,
            text="Open correlation groups JSON editor",
            command=self._open_table_correlation_groups_editor,
        )
        self.table_correlation_groups_editor_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.apply_table_btn = ttk.Button(right_box, text="Apply table changes", command=self._apply_table_changes)
        self.apply_table_btn.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        return panel

    def build_columns_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.schema_tab, "Columns", collapsed=True)
        panel.pack(fill="both", expand=True, pady=(0, 10))
        self.columns_panel = panel

        panel.body.columnconfigure(0, weight=1)
        panel.body.rowconfigure(1, weight=1)

        editor_box = ttk.LabelFrame(panel.body, text="Column editor", padding=8)
        editor_box.grid(row=0, column=0, sticky="ew")
        editor_box.columnconfigure(0, weight=1)

        column_form_frame = ttk.Frame(editor_box)
        column_form_frame.grid(row=0, column=0, sticky="ew")
        column_form = FormBuilder(column_form_frame)

        self.col_name_entry = column_form.add_entry("Column name", self.col_name_var)
        self.col_dtype_combo = column_form.add_combo("DType", self.col_dtype_var, DTYPES, readonly=True)
        self.col_min_entry = column_form.add_entry("Min value", self.col_min_var, width=12)
        self.col_max_entry = column_form.add_entry("Max value", self.col_max_var, width=12)
        self.col_choices_entry = column_form.add_entry("Choices (comma-separated)", self.col_choices_var)
        self.col_pattern_entry = column_form.add_entry("Regex pattern", self.col_pattern_var)
        self.col_pattern_entry.bind("<FocusOut>", self._on_pattern_entry_focus_out)
        self.col_pattern_preset_combo = column_form.add_combo(
            "Pattern preset",
            self.col_pattern_preset_var,
            list(PATTERN_PRESETS.keys()),
            readonly=True,
        )
        self.col_pattern_preset_combo.bind("<<ComboboxSelected>>", self._on_pattern_preset_selected)
        self.col_generator_combo = column_form.add_combo("Generator", self.col_generator_var, GENERATORS, readonly=True)
        self.col_params_entry = column_form.add_entry("Generator params JSON", self.col_params_var)
        self.col_depends_entry = column_form.add_entry("Depends on column", self.col_depends_var)

        self.col_params_template_btn = ttk.Button(
            editor_box,
            text="Fill params template for selected generator",
            command=self._apply_generator_params_template,
        )
        self.col_params_template_btn.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.col_params_editor_btn = ttk.Button(
            editor_box,
            text="Open params JSON editor",
            command=self._open_params_json_editor,
        )
        self.col_params_editor_btn.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        checks = ttk.Frame(editor_box)
        checks.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.col_nullable_chk = ttk.Checkbutton(checks, text="Nullable", variable=self.col_nullable_var)
        self.col_nullable_chk.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.col_pk_chk = ttk.Checkbutton(checks, text="Primary key (int only)", variable=self.col_pk_var)
        self.col_pk_chk.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.col_unique_chk = ttk.Checkbutton(checks, text="Unique", variable=self.col_unique_var)
        self.col_unique_chk.grid(row=0, column=2, sticky="w")

        self.add_col_btn = ttk.Button(editor_box, text="Add column to selected table", command=self._add_column)
        self.add_col_btn.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.edit_col_btn = ttk.Button(
            editor_box,
            text="Apply edits to selected column",
            command=self._apply_selected_column_changes,
        )
        self.edit_col_btn.grid(row=5, column=0, sticky="ew", pady=(6, 0))

        columns_box = ttk.LabelFrame(panel.body, text="Columns in selected table", padding=8)
        columns_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        columns_box.columnconfigure(0, weight=1)
        columns_box.rowconfigure(1, weight=1)

        self.columns_search = SearchEntry(columns_box, on_change=self._on_columns_search_change, delay_ms=150)
        self.columns_search.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.columns_table = TableView(columns_box, height=8)
        self.columns_table.grid(row=1, column=0, sticky="nsew")
        self.columns_table.set_columns(["name", "dtype", "nullable", "pk", "unique", "min", "max", "choices", "pattern"])
        self.columns_tree = self.columns_table.tree
        self.columns_tree.column("name", width=140)
        self.columns_tree.column("choices", width=180)
        self.columns_tree.column("pattern", width=180)
        self.columns_tree.bind("<<TreeviewSelect>>", self._on_column_selected)

        columns_page = ttk.Frame(columns_box)
        columns_page.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        columns_page.columnconfigure(1, weight=1)
        self.columns_prev_btn = ttk.Button(columns_page, text="Prev page", width=9, command=self._on_columns_filter_prev_page)
        self.columns_prev_btn.grid(row=0, column=0, sticky="w")
        self.columns_page_var = tk.StringVar(value="No rows.")
        ttk.Label(columns_page, textvariable=self.columns_page_var).grid(row=0, column=1, sticky="w", padx=(8, 8))
        self.columns_next_btn = ttk.Button(columns_page, text="Next page", width=9, command=self._on_columns_filter_next_page)
        self.columns_next_btn.grid(row=0, column=2, sticky="e")

        column_actions = ttk.Frame(columns_box)
        column_actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        column_actions.columnconfigure(0, weight=1)
        ttk.Button(column_actions, text="Remove selected column", command=self._remove_selected_column).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 4),
        )
        ttk.Button(column_actions, text="Move up", command=self._move_column_up).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(column_actions, text="Move down", command=self._move_column_down).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        return panel

    def build_relationships_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.schema_tab, "Relationships", collapsed=True)
        panel.pack(fill="both", expand=True, pady=(0, 10))
        self.relationships_panel = panel

        panel.body.columnconfigure(0, weight=1)
        panel.body.rowconfigure(1, weight=1)

        rel_box = ttk.LabelFrame(panel.body, text="Foreign key relationships", padding=8)
        rel_box.grid(row=0, column=0, sticky="ew")
        rel_box.columnconfigure(0, weight=1)

        rel_form_frame = ttk.Frame(rel_box)
        rel_form_frame.grid(row=0, column=0, sticky="ew")
        rel_form = FormBuilder(rel_form_frame)
        self.fk_parent_combo = rel_form.add_combo("Parent table", self.fk_parent_table_var, [], readonly=True)
        self.fk_parent_combo.bind("<<ComboboxSelected>>", self._on_fk_selection_changed)
        self.fk_child_combo = rel_form.add_combo("Child table", self.fk_child_table_var, [], readonly=True)
        self.fk_child_combo.bind("<<ComboboxSelected>>", self._on_fk_selection_changed)
        self.fk_child_col_combo = rel_form.add_combo("Child FK column (int)", self.fk_child_column_var, [], readonly=True)
        self.fk_min_entry = rel_form.add_entry("Min children", self.fk_min_children_var, width=8)
        self.fk_max_entry = rel_form.add_entry("Max children", self.fk_max_children_var, width=8)

        self.add_fk_btn = ttk.Button(rel_box, text="Add relationship", command=self._add_fk)
        self.add_fk_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        list_box = ttk.LabelFrame(panel.body, text="Defined relationships", padding=8)
        list_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        list_box.columnconfigure(0, weight=1)
        list_box.rowconfigure(1, weight=1)

        self.fk_search = SearchEntry(list_box, on_change=self._on_fk_search_change, delay_ms=150)
        self.fk_search.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.fks_table = TableView(list_box, height=8)
        self.fks_table.grid(row=1, column=0, sticky="nsew")
        self.fks_table.set_columns(["parent", "parent_pk", "child", "child_fk", "min", "max"])
        self.fks_tree = self.fks_table.tree
        self.fks_tree.column("parent", width=110)
        self.fks_tree.column("child", width=110)
        self.fks_tree.column("parent_pk", width=90)
        self.fks_tree.column("child_fk", width=90)
        self.fks_tree.column("min", width=60, anchor="e")
        self.fks_tree.column("max", width=60, anchor="e")

        fk_page = ttk.Frame(list_box)
        fk_page.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        fk_page.columnconfigure(1, weight=1)
        self.fks_prev_btn = ttk.Button(fk_page, text="Prev page", width=9, command=self._on_fk_filter_prev_page)
        self.fks_prev_btn.grid(row=0, column=0, sticky="w")
        self.fks_page_var = tk.StringVar(value="No rows.")
        ttk.Label(fk_page, textvariable=self.fks_page_var).grid(row=0, column=1, sticky="w", padx=(8, 8))
        self.fks_next_btn = ttk.Button(fk_page, text="Next page", width=9, command=self._on_fk_filter_next_page)
        self.fks_next_btn.grid(row=0, column=2, sticky="e")

        self.remove_fk_btn = ttk.Button(list_box, text="Remove selected relationship", command=self._remove_selected_fk)
        self.remove_fk_btn.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        self.relationships_empty_hint_var = tk.StringVar(value="")
        self.relationships_empty_hint_label = ttk.Label(
            list_box,
            textvariable=self.relationships_empty_hint_var,
            justify="left",
            wraplength=700,
        )
        self.relationships_empty_hint_label.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        return panel

    def build_generate_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.generate_tab, "Generate / Preview / Export / SQLite", collapsed=False)
        panel.pack(fill="both", expand=True)
        self.generate_panel = panel

        panel.body.columnconfigure(0, weight=1)
        panel.body.rowconfigure(3, weight=1)

        top_box = ttk.LabelFrame(panel.body, text="Output", padding=8)
        top_box.grid(row=0, column=0, sticky="ew")
        top_box.columnconfigure(1, weight=1)

        ttk.Label(top_box, text="SQLite DB path:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        self.db_path_entry = ttk.Entry(top_box, textvariable=self.db_path_var)
        self.db_path_entry.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(top_box, text="Browse...", command=self._browse_db_path).grid(row=0, column=2, sticky="ew", pady=4, padx=(8, 0))

        ttk.Label(top_box, text="Export format:").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        self.export_option_combo = ttk.Combobox(
            top_box,
            values=EXPORT_OPTIONS,
            textvariable=self.export_option_var,
            state="readonly",
        )
        self.export_option_combo.grid(row=1, column=1, sticky="ew", pady=4)

        actions = ttk.Frame(panel.body)
        actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        actions.columnconfigure(3, weight=1)

        self.generate_btn = ttk.Button(actions, text="Generate data (all tables)", command=self._on_generate_project)
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.export_btn = ttk.Button(actions, text="Export data", command=self._on_export_data)
        self.export_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.sample_btn = ttk.Button(actions, text="Generate sample (10 rows/table)", command=self._on_generate_sample)
        self.sample_btn.grid(row=0, column=2, sticky="ew", padx=4)

        self.clear_btn = ttk.Button(actions, text="Clear generated data", command=self._clear_generated)
        self.clear_btn.grid(row=0, column=3, sticky="ew", padx=(4, 0))

        self.generate_empty_hint_var = tk.StringVar(value="")
        self.generate_empty_hint_label = ttk.Label(
            panel.body,
            textvariable=self.generate_empty_hint_var,
            justify="left",
            wraplength=900,
        )
        self.generate_empty_hint_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        preview_box = ttk.LabelFrame(panel.body, text="Preview", padding=8)
        preview_box.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        preview_box.columnconfigure(1, weight=1)
        preview_box.rowconfigure(0, weight=1)

        left_preview = ttk.Frame(preview_box)
        left_preview.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_preview.columnconfigure(0, weight=1)

        ttk.Label(left_preview, text="Preview table:").grid(row=0, column=0, sticky="w")
        self.preview_table_combo = ttk.Combobox(left_preview, textvariable=self.preview_table_var, state="readonly")
        self.preview_table_combo.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.preview_table_combo.bind("<<ComboboxSelected>>", self._on_preview_table_selected)

        ttk.Label(left_preview, text="Row limit:").grid(row=2, column=0, sticky="w")
        self.preview_limit_var = tk.StringVar(value="200")
        self.preview_limit_entry = ttk.Entry(left_preview, textvariable=self.preview_limit_var, width=10)
        self.preview_limit_entry.grid(row=3, column=0, sticky="w", pady=(0, 8))

        ttk.Label(left_preview, text="Page size:").grid(row=4, column=0, sticky="w")
        self.preview_page_size_var = tk.StringVar(value="100")
        self.preview_page_size_combo = ttk.Combobox(
            left_preview,
            textvariable=self.preview_page_size_var,
            values=["50", "100", "200", "500"],
            width=8,
            state="readonly",
        )
        self.preview_page_size_combo.grid(row=5, column=0, sticky="w", pady=(0, 8))
        self.preview_page_size_combo.bind("<<ComboboxSelected>>", self._on_preview_page_size_changed)

        self.preview_btn = ttk.Button(left_preview, text="Refresh preview", command=self._refresh_preview)
        self.preview_btn.grid(row=6, column=0, sticky="ew")
        self.preview_columns_btn = ttk.Button(
            left_preview,
            text="Choose preview columns",
            command=self._open_preview_column_chooser,
        )
        self.preview_columns_btn.grid(row=7, column=0, sticky="ew", pady=(6, 0))

        self.progress = ttk.Progressbar(left_preview, mode="indeterminate")
        self.progress.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        self.register_busy_indicator(self.progress)

        right_preview = ttk.Frame(preview_box)
        right_preview.grid(row=0, column=1, sticky="nsew")
        right_preview.columnconfigure(0, weight=1)
        right_preview.rowconfigure(0, weight=1)

        self.preview_table = TableView(right_preview, height=12)
        self.preview_table.grid(row=0, column=0, sticky="nsew")
        self.preview_table.configure_large_data_mode(
            enabled=True,
            threshold_rows=1000,
            chunk_size=150,
            auto_pagination=False,
            auto_page_size=100,
        )
        self.preview_table.enable_pagination(page_size=100)
        self.preview_tree = self.preview_table.tree
        return panel

    def build_status_bar(self) -> ttk.Frame:
        return BaseScreen.build_status_bar(self, self._root_content, include_progress=False)

    def _on_back_requested(self) -> None:
        if self.confirm_discard_or_save(action_name="returning to Home"):
            self.app.go_home()

    def _refresh_inline_validation_summary(self, issues: list[ValidationIssue] | None = None) -> None:
        if not hasattr(self, "inline_validation"):
            return

        entries: list[InlineValidationEntry] = []
        issue_list = issues if issues is not None else self._validate_project_detailed(self.project)
        for issue in issue_list:
            location = "Project"
            if issue.scope == "fk":
                fk_table = issue.table or "unknown_child"
                fk_column = issue.column or "unknown_column"
                location = f"FK {fk_table}.{fk_column}"
            elif issue.table is not None and issue.column is not None:
                location = f"Table '{issue.table}', column '{issue.column}'"
            elif issue.table is not None:
                location = f"Table '{issue.table}'"
            entries.append(
                InlineValidationEntry(
                    severity=issue.severity,
                    location=location,
                    message=issue.message,
                    jump_payload=issue,
                )
            )
        self.inline_validation.set_entries(entries)

    def _jump_to_validation_issue(self, entry: InlineValidationEntry) -> None:
        payload = entry.jump_payload
        if not isinstance(payload, ValidationIssue):
            return

        self.main_tabs.select(self.schema_tab)
        if payload.scope == "fk":
            self._jump_to_fk_issue(payload.table, payload.column)
            return
        self._jump_to_table_or_column_issue(payload.table, payload.column)

    def _jump_to_table_or_column_issue(self, table_name: str | None, column_name: str | None) -> None:
        if table_name is None:
            return

        for index, table in enumerate(self.project.tables):
            if table.table_name != table_name:
                continue

            self.tables_panel.expand()
            self.columns_panel.expand()
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(index)
            self.tables_list.activate(index)
            self.tables_list.see(index)
            self._on_table_selected()
            if column_name:
                col_idx = next((i for i, col in enumerate(self.project.tables[index].columns) if col.name == column_name), None)
                if col_idx is not None:
                    if hasattr(self, "columns_search") and self.columns_search.query_var.get().strip():
                        self.columns_search.query_var.set("")
                        self._on_columns_search_change("")
                    self._show_column_source_index(col_idx)
                    if self.columns_tree.selection():
                        self._on_column_selected()
            self.set_status(
                f"Jumped to validation location: table '{table_name}'"
                + (f", column '{column_name}'." if column_name else ".")
            )
            return

        self.set_status(
            f"Validation jump: table '{table_name}' was not found. "
            "Fix: re-run validation to refresh issue locations."
        )

    def _jump_to_fk_issue(self, child_table: str | None, child_column: str | None) -> None:
        self.relationships_panel.expand()
        if child_table is None:
            return
        target_index: int | None = None
        for idx, fk in enumerate(self.project.foreign_keys):
            if fk.child_table != child_table:
                continue
            if child_column is not None and fk.child_column != child_column:
                continue
            target_index = idx
            break
        if target_index is not None:
            if hasattr(self, "fk_search") and self.fk_search.query_var.get().strip():
                self.fk_search.query_var.set("")
                self._on_fk_search_change("")
            self._show_fk_source_index(target_index)
            if self.fks_tree.selection():
                row = self.project.foreign_keys[target_index]
                self.set_status(
                    f"Jumped to validation location: FK '{row.child_table}.{row.child_column}'."
                )
                return
        self.set_status(
            f"Validation jump: FK '{child_table}.{child_column or ''}' was not found. "
            "Fix: re-run validation to refresh issue locations."
        )

    def _preview_columns_for_table(self, table_name: str) -> list[str]:
        for table in self.project.tables:
            if table.table_name == table_name:
                return [column.name for column in table.columns]
        if self._preview_source_rows:
            return list(self._preview_source_rows[0].keys())
        return []

    def _refresh_preview_projection(self) -> None:
        table_name = self._preview_source_table
        if table_name == "":
            self._clear_preview_tree()
            return

        schema_columns = self._preview_columns_for_table(table_name)
        if not schema_columns and self._preview_source_rows:
            schema_columns = list(self._preview_source_rows[0].keys())
        if not schema_columns:
            self._clear_preview_tree()
            return

        visible_columns = self._preview_column_preferences.get(table_name, list(schema_columns))
        visible_columns = [name for name in visible_columns if name in schema_columns]
        if not visible_columns:
            visible_columns = list(schema_columns)
            self._preview_column_preferences[table_name] = list(visible_columns)

        projected_rows: list[dict[str, object]] = []
        for row in self._preview_source_rows:
            projected_rows.append({name: row.get(name, "") for name in visible_columns})

        self.preview_table.set_columns(visible_columns)
        self.preview_table.set_rows(projected_rows)
        self._on_preview_page_size_changed()

    def _on_preview_page_size_changed(self, _event=None) -> None:
        if not hasattr(self, "preview_table"):
            return
        try:
            page_size = int(self.preview_page_size_var.get().strip())
            self.preview_table.set_page_size(page_size)
            self._persist_workspace_state()
        except Exception as exc:
            self._show_error_dialog(
                "Preview page size",
                f"Preview page size: invalid value '{self.preview_page_size_var.get()}'. "
                f"Fix: choose one of 50, 100, 200, or 500. Details: {exc}",
            )
            self.preview_page_size_var.set(str(self.preview_table.page_size))

    def _open_preview_column_chooser(self) -> None:
        table_name = self.preview_table_var.get().strip()
        if table_name == "":
            self._show_error_dialog(
                "Preview columns",
                "Preview columns: no preview table is selected. "
                "Fix: choose a preview table first.",
            )
            return

        columns = self._preview_columns_for_table(table_name)
        if not columns:
            self._show_error_dialog(
                "Preview columns",
                f"Preview columns: table '{table_name}' has no columns to configure. "
                "Fix: select a table with generated preview data.",
            )
            return

        ColumnChooserDialog(
            self,
            columns=columns,
            visible_columns=self._preview_column_preferences.get(table_name, list(columns)),
            on_apply=lambda selected: self._on_preview_columns_applied(table_name, selected),
            title=f"Preview columns: {table_name}",
        )

    def _on_preview_columns_applied(self, table_name: str, selected_columns: list[str]) -> None:
        self._preview_column_preferences[table_name] = list(selected_columns)
        self._refresh_preview_projection()
        self._persist_workspace_state()
        self._show_toast("Applied preview column visibility/order.", level="success")

    def _mark_dirty_if_project_changed(self, before_project, *, reason: str) -> None:
        if self.project != before_project:
            self.mark_dirty(reason)

    def _workspace_store(self) -> WorkspacePreferencesStore | None:
        store = getattr(self.app, "workspace_preferences", None)
        if isinstance(store, WorkspacePreferencesStore):
            return store
        return None

    def _workspace_panel_state(self) -> dict[str, bool]:
        state: dict[str, bool] = {}
        for panel_key in ("project", "tables", "columns", "relationships", "generate"):
            panel = getattr(self, f"{panel_key}_panel", None)
            if isinstance(panel, CollapsiblePanel):
                state[panel_key] = bool(panel.is_collapsed)
        return state

    def _workspace_preview_column_state(self) -> dict[str, list[str]]:
        payload: dict[str, list[str]] = {}
        for table_name, columns in self._preview_column_preferences.items():
            if not isinstance(table_name, str):
                continue
            clean_table = table_name.strip()
            if clean_table == "":
                continue
            if not isinstance(columns, list):
                continue
            clean_columns = [str(col).strip() for col in columns if str(col).strip() != ""]
            if not clean_columns:
                continue
            payload[clean_table] = clean_columns
        return payload

    def _workspace_state_payload(self) -> dict[str, object]:
        tab_index = 0
        try:
            selected_tab = self.main_tabs.select()
            if selected_tab:
                tab_index = int(self.main_tabs.index(selected_tab))
        except Exception:
            tab_index = 0
        page_size = self.preview_page_size_var.get().strip()
        return {
            "version": 1,
            "main_tab_index": tab_index,
            "panel_state": self._workspace_panel_state(),
            "preview_page_size": page_size,
            "preview_column_preferences": self._workspace_preview_column_state(),
        }

    def _persist_workspace_state(self) -> None:
        store = self._workspace_store()
        if store is None:
            return
        try:
            payload = self._workspace_state_payload()
        except Exception:
            return
        try:
            store.save_route_state(self.WORKSPACE_STATE_ROUTE_KEY, payload)
        except Exception:
            # Workspace-state persistence is best-effort and must not break route behavior.
            return

    def _restore_workspace_state(self) -> None:
        store = self._workspace_store()
        if store is None:
            return
        try:
            payload = store.get_route_state(self.WORKSPACE_STATE_ROUTE_KEY)
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        raw_columns = payload.get("preview_column_preferences")
        if isinstance(raw_columns, dict):
            restored_columns: dict[str, list[str]] = {}
            for table_name, columns in raw_columns.items():
                if not isinstance(table_name, str) or not isinstance(columns, list):
                    continue
                clean_table = table_name.strip()
                if clean_table == "":
                    continue
                clean_columns = [str(col).strip() for col in columns if str(col).strip() != ""]
                if clean_columns:
                    restored_columns[clean_table] = clean_columns
            self._preview_column_preferences = restored_columns

        page_size_raw = payload.get("preview_page_size")
        page_size_text = str(page_size_raw).strip() if page_size_raw is not None else ""
        if page_size_text != "":
            try:
                page_size_value = int(page_size_text)
                if page_size_value > 0:
                    self.preview_page_size_var.set(str(page_size_value))
                    self.preview_table.set_page_size(page_size_value)
            except Exception:
                pass

        panel_state = payload.get("panel_state")
        if isinstance(panel_state, dict):
            for panel_key, collapsed in panel_state.items():
                if not isinstance(panel_key, str):
                    continue
                panel = getattr(self, f"{panel_key}_panel", None)
                if not isinstance(panel, CollapsiblePanel):
                    continue
                should_collapse = bool(collapsed)
                if should_collapse:
                    panel.collapse()
                else:
                    panel.expand()

        tab_index_raw = payload.get("main_tab_index")
        try:
            tab_index = int(tab_index_raw)
        except Exception:
            tab_index = 0
        tab_count = len(self.main_tabs.tabs())
        if tab_count <= 0:
            return
        normalized = min(max(0, tab_index), tab_count - 1)
        self.main_tabs.select(normalized)

    def _on_main_tab_changed(self, _event=None) -> None:
        self._persist_workspace_state()

    def _capture_undo_snapshot(self) -> EditorUndoSnapshot:
        selected_column_index: int | None = None
        selected_fk_index: int | None = None
        try:
            selected_column_index = self._selected_column_index()
        except Exception:
            selected_column_index = None
        try:
            selected_fk_index = self._selected_fk_index()
        except Exception:
            selected_fk_index = None
        return EditorUndoSnapshot(
            project=self.project,
            selected_table_index=self.selected_table_index,
            selected_column_index=selected_column_index,
            selected_fk_index=selected_fk_index,
        )

    def _apply_undo_snapshot(self, snapshot: EditorUndoSnapshot) -> None:
        self._cancel_validation_debounce()
        self._suspend_project_meta_dirty = True
        try:
            self.project = snapshot.project
            self.project_name_var.set(self.project.name)
            self.seed_var.set(str(self.project.seed))
            self.project_timeline_constraints_var.set(
                json.dumps(self.project.timeline_constraints, sort_keys=True) if self.project.timeline_constraints else ""
            )
        finally:
            self._suspend_project_meta_dirty = False

        self.selected_table_index = None
        self._refresh_tables_list()
        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

        target_table_index = snapshot.selected_table_index
        if target_table_index is not None and 0 <= target_table_index < len(self.project.tables):
            self.selected_table_index = target_table_index
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(target_table_index)
            self.tables_list.activate(target_table_index)
            self.tables_list.see(target_table_index)
            self._load_selected_table_into_editor()
        else:
            self._set_table_editor_enabled(False)
            self._clear_column_editor()
            self._refresh_columns_tree()

        if snapshot.selected_column_index is not None:
            self._show_column_source_index(snapshot.selected_column_index)
            if self.columns_tree.selection():
                self._on_column_selected()

        if snapshot.selected_fk_index is not None:
            self._show_fk_source_index(snapshot.selected_fk_index)

        self._stage_full_validation()
        self._run_validation_full()

    def _record_undo_snapshot(
        self,
        *,
        before: EditorUndoSnapshot,
        label: str,
        reason: str,
    ) -> None:
        after = self._capture_undo_snapshot()
        if after.project == before.project:
            self._update_undo_redo_controls()
            return
        command = SnapshotCommand[EditorUndoSnapshot](
            label=label,
            apply_state=self._apply_undo_snapshot,
            before_state=before,
            after_state=after,
        )
        self.undo_stack.push(command)
        self._sync_dirty_from_saved_baseline(default_reason=reason)
        self._update_undo_redo_controls()

    def _sync_dirty_from_saved_baseline(self, *, default_reason: str) -> None:
        if self.project == self._undo_saved_project:
            self.mark_clean()
            return
        self.mark_dirty(default_reason)

    def _mark_saved_baseline(self) -> None:
        self._undo_saved_project = self.project
        self.mark_clean()
        self._update_undo_redo_controls()

    def _reset_undo_history(self) -> None:
        self.undo_stack.clear()
        self._undo_saved_project = self.project
        self.mark_clean()
        self._update_undo_redo_controls()

    def _undo_blocker_reason(self) -> str | None:
        if self.is_running:
            return (
                "Cannot modify undo/redo history while generation/export is running. "
                "Fix: wait for the active run to finish or cancel it."
            )
        if self._project_io_busy():
            return (
                "Cannot modify undo/redo history while project save/load is running. "
                "Fix: wait for project save/load to finish."
            )
        return None

    def _update_undo_redo_controls(self) -> None:
        undo_btn = getattr(self, "undo_btn", None)
        redo_btn = getattr(self, "redo_btn", None)
        if undo_btn is None or redo_btn is None:
            return

        blocker = self._undo_blocker_reason()
        can_undo = blocker is None and self.undo_stack.can_undo
        can_redo = blocker is None and self.undo_stack.can_redo
        undo_btn.configure(state=(tk.NORMAL if can_undo else tk.DISABLED))
        redo_btn.configure(state=(tk.NORMAL if can_redo else tk.DISABLED))

        undo_label = self.undo_stack.undo_label
        redo_label = self.undo_stack.redo_label
        undo_text = "Undo" if not undo_label else f"Undo: {undo_label}"
        redo_text = "Redo" if not redo_label else f"Redo: {redo_label}"
        undo_btn.configure(text=undo_text)
        redo_btn.configure(text=redo_text)

    def _undo_last_change(self) -> None:
        blocker = self._undo_blocker_reason()
        if blocker is not None:
            self.set_status(blocker)
            return
        try:
            command = self.undo_stack.undo()
        except Exception as exc:
            self._show_error_dialog(
                "Undo failed",
                f"Undo action: failed to apply previous schema state ({exc}). "
                "Fix: retry undo or continue editing and save/load project state.",
            )
            self._update_undo_redo_controls()
            return
        if command is None:
            self.set_status("Undo: no changes available.")
            self._update_undo_redo_controls()
            return
        self._sync_dirty_from_saved_baseline(default_reason="undo/redo changes")
        self._update_undo_redo_controls()
        self.set_status(f"Undo complete: {command.label}.")

    def _redo_last_change(self) -> None:
        blocker = self._undo_blocker_reason()
        if blocker is not None:
            self.set_status(blocker)
            return
        try:
            command = self.undo_stack.redo()
        except Exception as exc:
            self._show_error_dialog(
                "Redo failed",
                f"Redo action: failed to re-apply schema state ({exc}). "
                "Fix: retry redo or continue editing and save/load project state.",
            )
            self._update_undo_redo_controls()
            return
        if command is None:
            self.set_status("Redo: no changes available.")
            self._update_undo_redo_controls()
            return
        self._sync_dirty_from_saved_baseline(default_reason="undo/redo changes")
        self._update_undo_redo_controls()
        self.set_status(f"Redo complete: {command.label}.")

    def _on_project_meta_changed(self, *_args) -> None:
        if getattr(self, "_suspend_project_meta_dirty", False):
            return
        self.mark_dirty("project settings")

    def _register_shortcuts(self) -> None:
        self.shortcut_manager.register_ctrl_cmd("s", "Save project JSON", self._start_save_project_async)
        self.shortcut_manager.register_ctrl_cmd("o", "Load project JSON", self._start_load_project_async)
        self.shortcut_manager.register_ctrl_cmd("z", "Undo last schema edit", self._undo_last_change)
        self.shortcut_manager.register_ctrl_cmd("y", "Redo last schema edit", self._redo_last_change)
        self.shortcut_manager.register_ctrl_cmd(
            "z",
            "Redo last schema edit",
            self._redo_last_change,
            shift=True,
        )
        self.shortcut_manager.register_ctrl_cmd("f", "Focus table search", self._focus_table_search)
        self.shortcut_manager.register_ctrl_cmd(
            "f",
            "Focus column search",
            self._focus_columns_search,
            shift=True,
        )
        self.shortcut_manager.register_ctrl_cmd("g", "Focus relationship search", self._focus_fk_search)
        self.shortcut_manager.register("<F5>", "Run validation", self._run_validation_full)
        self.shortcut_manager.register_ctrl_cmd("Return", "Generate data", self._on_generate_project)
        self.shortcut_manager.register("<F6>", "Focus next major section", self._focus_next_anchor)
        self.shortcut_manager.register("<Shift-F6>", "Focus previous major section", self._focus_previous_anchor)
        self.shortcut_manager.register("<F1>", "Open shortcuts help", self._show_shortcuts_help)
        self.shortcut_manager.register_help_item("Ctrl/Cmd+C", "Copy selected table rows with headers")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Shift+C", "Copy selected table rows without headers")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+A", "Select all rows in focused table")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Z", "Undo last schema edit")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Y", "Redo last schema edit")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Shift+Z", "Redo last schema edit")
        self.shortcut_manager.register_help_item("PageUp/PageDown", "Move selection by page in focused table")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Home", "Jump to first row in focused table")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+End", "Jump to last row in focused table")

    def _register_focus_anchors(self) -> None:
        self.focus_controller.add_anchor(
            "project_name",
            lambda: getattr(self, "project_name_entry", None),
            description="Project name",
        )
        self.focus_controller.add_anchor(
            "tables_search",
            lambda: getattr(getattr(self, "tables_search", None), "entry", None),
            description="Table search",
        )
        self.focus_controller.add_anchor(
            "columns_search",
            lambda: getattr(getattr(self, "columns_search", None), "entry", None),
            description="Columns search",
        )
        self.focus_controller.add_anchor(
            "fk_search",
            lambda: getattr(getattr(self, "fk_search", None), "entry", None),
            description="Relationships search",
        )
        self.focus_controller.add_anchor(
            "preview_table",
            lambda: getattr(self, "preview_table_combo", None),
            description="Preview table selector",
        )
        self.focus_controller.set_default_anchor("project_name")

    def _on_screen_destroy(self, event) -> None:
        if event.widget is self:
            self._persist_workspace_state()
            self._cancel_validation_debounce()

    @staticmethod
    def _starter_fixture_abspath() -> Path:
        return Path(__file__).resolve().parents[1] / STARTER_FIXTURE_PATH

    @staticmethod
    def _build_starter_project(seed: int) -> SchemaProject:
        customers = TableSpec(
            table_name="customers",
            row_count=120,
            columns=[
                ColumnSpec(name="customer_id", dtype="int", nullable=False, primary_key=True),
                ColumnSpec(name="customer_name", dtype="text", nullable=False),
                ColumnSpec(
                    name="segment",
                    dtype="text",
                    nullable=False,
                    generator="choice_weighted",
                    params={"choices": ["enterprise", "mid_market", "consumer"], "weights": [0.2, 0.3, 0.5]},
                ),
            ],
        )
        orders = TableSpec(
            table_name="orders",
            row_count=300,
            columns=[
                ColumnSpec(name="order_id", dtype="int", nullable=False, primary_key=True),
                ColumnSpec(name="customer_id", dtype="int", nullable=False),
                ColumnSpec(
                    name="order_total",
                    dtype="decimal",
                    nullable=False,
                    generator="money",
                    params={"min": 5.0, "max": 750.0, "decimals": 2},
                ),
                ColumnSpec(
                    name="ordered_at",
                    dtype="datetime",
                    nullable=False,
                    generator="timestamp_utc",
                    params={"start": "2024-01-01T00:00:00Z", "end": "2026-12-31T23:59:59Z"},
                ),
            ],
        )
        return SchemaProject(
            name="starter_project",
            seed=seed,
            tables=[customers, orders],
            foreign_keys=[
                ForeignKeySpec(
                    parent_table="customers",
                    parent_column="customer_id",
                    child_table="orders",
                    child_column="customer_id",
                    min_children=1,
                    max_children=4,
                )
            ],
            timeline_constraints=None,
        )

    def _create_starter_schema(self) -> None:
        if not self._project_io_guard(action="create starter schema"):
            return
        if self.project.tables and not self.confirm_discard_or_save(action_name="creating a starter schema"):
            return

        try:
            starter_seed = int(self.seed_var.get().strip())
        except Exception:
            starter_seed = int(getattr(self.cfg, "seed", 12345))

        try:
            project = self._build_starter_project(starter_seed)
            validate_project(project)
        except Exception as exc:
            self._show_error_dialog(
                "Starter schema",
                f"First-run quick start: could not build starter schema ({exc}). "
                "Fix: create a table manually or load a valid project JSON file.",
            )
            return

        self._apply_loaded_project(project, "starter schema (built-in)")
        self.set_status(
            "Starter schema ready. Next action: open Generate tab and click 'Generate sample (10 rows/table)'."
        )
        self._show_toast("Starter schema created.", level="success")

    def _load_starter_fixture_shortcut(self) -> None:
        if not self._project_io_guard(action="load starter fixture"):
            return
        if self.project.tables and not self.confirm_discard_or_save(action_name="loading starter fixture"):
            return

        fixture_path = self._starter_fixture_abspath()
        if not fixture_path.exists():
            self._show_error_dialog(
                "Starter fixture",
                "First-run quick start: starter fixture 'tests/fixtures/default_schema_project.json' was not found. "
                "Fix: restore the fixture file or use 'Create starter schema'.",
            )
            return

        try:
            project = load_project_from_json(str(fixture_path))
        except Exception as exc:
            self._show_error_dialog(
                "Starter fixture",
                f"First-run quick start: failed to load starter fixture ({exc}). "
                "Fix: use 'Create starter schema' or choose a valid project JSON file.",
            )
            return

        self._apply_loaded_project(project, STARTER_FIXTURE_PATH.as_posix())
        self.set_status(
            "Starter fixture loaded. Next action: open Generate tab and click 'Generate sample (10 rows/table)'."
        )
        self._show_toast("Starter fixture loaded.", level="success")

    def _refresh_onboarding_hints(self) -> None:
        table_count = len(self.project.tables)
        fk_count = len(self.project.foreign_keys)
        generated = getattr(self, "generated_rows", {})
        generated_row_count = sum(len(rows) for rows in generated.values()) if isinstance(generated, dict) else 0
        generated_table_count = len(generated) if isinstance(generated, dict) else 0
        preview_table = self.preview_table_var.get().strip() if hasattr(self, "preview_table_var") else ""

        if table_count == 0:
            project_hint = (
                "No schema tables yet. Next action: use 'Create starter schema' or 'Load starter fixture', "
                "or click '+ Add table' to author manually."
            )
            tables_hint = (
                "Empty state: no tables defined. Start with '+ Add table' or create a starter schema from the "
                "Project panel."
            )
            relationships_hint = (
                "Empty state: relationships appear after at least two tables exist. "
                "Add tables first, then map parent->child keys."
            )
            generate_hint = (
                "Empty state: no schema to generate. Next action: create/load a schema, then click "
                "'Generate sample (10 rows/table)'."
            )
        elif generated_row_count == 0:
            project_hint = (
                f"Schema ready ({table_count} table(s), {fk_count} relationship(s)). "
                "Next action: open Generate tab and run a sample preview."
            )
            tables_hint = (
                f"Schema contains {table_count} table(s). Select a table to edit columns, business keys, and SCD settings."
            )
            relationships_hint = (
                f"Schema contains {fk_count} relationship(s). Add/edit FK mappings to enforce parent-child generation rules."
            )
            generate_hint = "No preview rows yet. Next action: click 'Generate sample (10 rows/table)'."
        elif preview_table == "":
            project_hint = (
                f"Generated data ready ({generated_row_count} rows across {generated_table_count} table(s)). "
                "Next action: choose a preview table."
            )
            tables_hint = (
                f"Generated preview is available for {generated_table_count} table(s). "
                "Switch between tables to verify schema outputs."
            )
            relationships_hint = (
                f"Relationship graph currently has {fk_count} FK mapping(s). "
                "Adjust mappings if generated child distributions look off."
            )
            generate_hint = (
                f"Generated rows ready ({generated_row_count} total). Next action: pick a preview table to inspect rows."
            )
        else:
            project_hint = (
                f"Preview active for '{preview_table}'. Continue refining schema or export generated data when satisfied."
            )
            tables_hint = (
                f"Editing context: {table_count} table(s), {fk_count} relationship(s). "
                "Use Undo/Redo for safe iteration."
            )
            relationships_hint = (
                f"FK configuration has {fk_count} relationship(s). "
                "Use search and paging to review mappings on larger schemas."
            )
            generate_hint = (
                f"Preview table '{preview_table}' is loaded. Adjust row limit/page size or run export actions."
            )

        project_busy = bool(getattr(self, "_project_io_running", False))
        lifecycle = getattr(self, "project_io_lifecycle", None)
        if lifecycle is not None:
            try:
                project_busy = project_busy or bool(lifecycle.state.is_running)
            except Exception:
                pass
        actions_enabled = not bool(getattr(self, "is_running", False)) and not project_busy
        action_state = tk.NORMAL if actions_enabled else tk.DISABLED

        for widget_name in ("create_starter_schema_btn", "load_starter_fixture_btn", "open_generate_tab_btn"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.configure(state=action_state)

        if hasattr(self, "onboarding_project_hint_var"):
            self.onboarding_project_hint_var.set(project_hint)
        if hasattr(self, "tables_empty_hint_var"):
            self.tables_empty_hint_var.set(tables_hint)
        if hasattr(self, "relationships_empty_hint_var"):
            self.relationships_empty_hint_var.set(relationships_hint)
        if hasattr(self, "generate_empty_hint_var"):
            self.generate_empty_hint_var.set(generate_hint)

    def _cancel_validation_debounce(self) -> None:
        if self._validation_debounce_after_id is None:
            return
        try:
            self.after_cancel(self._validation_debounce_after_id)
        except tk.TclError:
            pass
        finally:
            self._validation_debounce_after_id = None
            self._validation_pending_tables.clear()
            self._validation_pending_mode = "full"

    def _stage_incremental_validation(self, *, table_names: Iterable[str]) -> None:
        clean_names = {name.strip() for name in table_names if isinstance(name, str) and name.strip() != ""}
        if not clean_names:
            return
        self._validation_pending_mode = "incremental"
        self._validation_pending_tables.update(clean_names)

    def _stage_full_validation(self) -> None:
        self._validation_pending_mode = "full"
        self._validation_pending_tables.clear()

    def _run_validation_full(self) -> None:
        self._run_validation(mode="full")

    def _run_validation(self, *, mode: str = "auto") -> None:
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"auto", "full", "incremental"}:
            normalized_mode = "auto"

        if normalized_mode == "full":
            self._cancel_validation_debounce()
            self._execute_full_validation()
            return

        if normalized_mode == "incremental":
            tables = set(self._validation_pending_tables)
            self._validation_pending_tables.clear()
            self._validation_pending_mode = "full"
            if tables:
                self._schedule_incremental_validation(tables)
            else:
                self._execute_full_validation()
            return

        if self._validation_pending_mode == "incremental" and self._validation_pending_tables:
            tables = set(self._validation_pending_tables)
            self._validation_pending_tables.clear()
            self._validation_pending_mode = "full"
            self._schedule_incremental_validation(tables)
            return

        self._validation_pending_mode = "full"
        self._validation_pending_tables.clear()
        self._cancel_validation_debounce()
        self._execute_full_validation()

    def _schedule_incremental_validation(self, table_names: set[str]) -> None:
        if not table_names:
            self._execute_full_validation()
            return
        self._validation_pending_tables.update(table_names)
        if self._validation_debounce_after_id is not None:
            return
        self.validation_summary_var.set("Validation: updating...")
        self._validation_debounce_after_id = self.after(
            VALIDATION_DEBOUNCE_MS,
            self._flush_incremental_validation,
        )

    def _flush_incremental_validation(self) -> None:
        self._validation_debounce_after_id = None
        tables = set(self._validation_pending_tables)
        self._validation_pending_tables.clear()
        if not tables:
            self._execute_full_validation()
            return
        self._execute_incremental_validation(tables)

    def _execute_full_validation(self) -> None:
        try:
            self._apply_project_vars_to_model()
        except Exception as exc:
            self._show_error_dialog("Project error", str(exc))
            return
        issues = self._validate_project_detailed(self.project)
        self._rebuild_validation_cache(issues)
        self._apply_validation_issues(issues)

    def _execute_incremental_validation(self, touched_tables: set[str]) -> None:
        if not self._validation_cache_table_issues and not self._validation_cache_project_issues:
            self._execute_full_validation()
            return
        try:
            self._apply_project_vars_to_model()
        except Exception as exc:
            self._show_error_dialog("Project error", str(exc))
            return

        expanded_tables = self._expand_incremental_scope_tables(touched_tables)
        if not expanded_tables:
            self._execute_full_validation()
            return

        projection = self._build_validation_projection(expanded_tables)
        issues = self._validate_project_detailed(projection)
        grouped = self._group_issues_by_table(issues)
        current_table_names = {table.table_name for table in self.project.tables}

        for stale in list(self._validation_cache_table_issues.keys()):
            if stale not in current_table_names:
                self._validation_cache_table_issues.pop(stale, None)
        for table_name in expanded_tables:
            if table_name in current_table_names:
                self._validation_cache_table_issues[table_name] = grouped.get(table_name, [])

        merged = self._merge_validation_cache()
        self._apply_validation_issues(merged)

    def _expand_incremental_scope_tables(self, touched_tables: set[str]) -> set[str]:
        existing_names = {table.table_name for table in self.project.tables}
        base = {name for name in touched_tables if name in existing_names}
        if not base:
            return set()
        expanded = set(base)
        for fk in self.project.foreign_keys:
            if fk.child_table in base or fk.parent_table in base:
                if fk.child_table in existing_names:
                    expanded.add(fk.child_table)
                if fk.parent_table in existing_names:
                    expanded.add(fk.parent_table)
        return expanded

    def _build_validation_projection(self, table_names: set[str]) -> SchemaProject:
        # Preserve original table order for deterministic projected validation.
        ordered_tables = [table for table in self.project.tables if table.table_name in table_names]
        projected_fks = [
            fk
            for fk in self.project.foreign_keys
            if fk.child_table in table_names and fk.parent_table in table_names
        ]
        projected_timeline_constraints: list[dict[str, object]] | None = None
        raw_rules = self.project.timeline_constraints or []
        if raw_rules:
            projected_rules: list[dict[str, object]] = []
            for raw_rule in raw_rules:
                if not isinstance(raw_rule, dict):
                    continue
                child_table = str(raw_rule.get("child_table", "")).strip()
                if child_table not in table_names:
                    continue
                references_raw = raw_rule.get("references")
                if not isinstance(references_raw, list):
                    continue
                filtered_references = [
                    dict(reference)
                    for reference in references_raw
                    if isinstance(reference, dict)
                    and str(reference.get("parent_table", "")).strip() in table_names
                ]
                if not filtered_references:
                    continue
                rule_copy = dict(raw_rule)
                rule_copy["references"] = filtered_references
                projected_rules.append(rule_copy)
            if projected_rules:
                projected_timeline_constraints = projected_rules
        return SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=ordered_tables,
            foreign_keys=projected_fks,
            timeline_constraints=projected_timeline_constraints,
        )

    @staticmethod
    def _group_issues_by_table(issues: list[ValidationIssue]) -> dict[str, list[ValidationIssue]]:
        grouped: dict[str, list[ValidationIssue]] = {}
        for issue in issues:
            if issue.table is None:
                continue
            grouped.setdefault(issue.table, []).append(issue)
        return grouped

    def _rebuild_validation_cache(self, issues: list[ValidationIssue]) -> None:
        grouped = self._group_issues_by_table(issues)
        self._validation_cache_project_issues = [issue for issue in issues if issue.table is None]
        self._validation_cache_table_issues = {
            table.table_name: grouped.get(table.table_name, [])
            for table in self.project.tables
        }

    def _merge_validation_cache(self) -> list[ValidationIssue]:
        merged = list(self._validation_cache_project_issues)
        for table in self.project.tables:
            merged.extend(self._validation_cache_table_issues.get(table.table_name, []))
        return merged

    def _apply_validation_issues(self, issues: list[ValidationIssue]) -> None:
        checks = ["PK", "Columns", "Dependencies", "Generator", "SCD/BK", "FKs"]
        tables = [table.table_name for table in self.project.tables]
        if any(issue.table is None for issue in issues):
            tables = ["Project"] + tables

        status: dict[tuple[str, str], str] = {(table, check): "ok" for table in tables for check in checks}
        details: dict[tuple[str, str], list[str]] = {}

        def mark(table: str, check: str, severity: str, message: str) -> None:
            key = (table, check)
            rank = {"ok": 0, "warn": 1, "error": 2}
            if rank.get(severity, 0) > rank.get(status.get(key, "ok"), 0):
                status[key] = severity
            details.setdefault(key, []).append(message)

        def classify_bucket(issue: ValidationIssue) -> str:
            if issue.scope == "fk":
                return "FKs"
            if issue.scope == "dependency":
                return "Dependencies"
            if issue.scope == "scd":
                return "SCD/BK"
            if issue.scope == "generator":
                return "Generator"

            text = issue.message.lower()
            if "depends_on" in text or "dependency" in text:
                return "Dependencies"
            if "scd" in text or "business_key" in text:
                return "SCD/BK"
            if "generator" in text or "params." in text:
                return "Generator"
            if "foreign key" in text or text.startswith("fk "):
                return "FKs"
            if "primary key" in text or " pk" in text:
                return "PK"
            return "Columns"

        for issue in issues:
            target_table = issue.table if issue.table is not None else "Project"
            if target_table not in tables:
                continue
            mark(target_table, classify_bucket(issue), issue.severity, issue.message)

        self.heatmap.set_data(tables=tables, checks=checks, status=status, details=details)
        self._refresh_inline_validation_summary(issues)

        errors = sum(1 for issue in issues if issue.severity == "error")
        warnings = sum(1 for issue in issues if issue.severity == "warn")
        self.last_validation_errors = errors
        self.last_validation_warnings = warnings
        self.validation_summary_var.set(
            f"Validation: {errors} errors, {warnings} warnings. Click cells for details."
        )
        self._update_generate_enabled()

    def _focus_table_search(self) -> None:
        if hasattr(self, "tables_search"):
            self.tables_search.focus()

    def _focus_columns_search(self) -> None:
        if hasattr(self, "columns_search"):
            self.columns_search.focus()

    def _focus_fk_search(self) -> None:
        if hasattr(self, "fk_search"):
            self.fk_search.focus()

    def _focus_next_anchor(self) -> None:
        self.focus_controller.focus_next()

    def _focus_previous_anchor(self) -> None:
        self.focus_controller.focus_previous()

    def _show_shortcuts_help(self) -> None:
        self.shortcut_manager.show_help_dialog(title="Schema Project Shortcuts")

    def _show_notifications_history(self) -> None:
        if hasattr(self, "toast_center"):
            self.toast_center.show_history_dialog(title="Schema Project Notifications")

    def _show_toast(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
        if hasattr(self, "toast_center"):
            self.toast_center.notify(message, level=level, duration_ms=duration_ms)

    def _open_params_json_editor(self) -> None:
        JsonEditorDialog(
            self,
            title="Generator Params JSON Editor",
            initial_text=self.col_params_var.get(),
            require_object=True,
            on_apply=self._on_params_json_apply,
        )

    def _on_params_json_apply(self, pretty_json: str) -> None:
        self.col_params_var.set(pretty_json)
        self.set_status("Applied JSON editor content to Generator params JSON.")
        self._show_toast("Generator params updated from JSON editor.", level="success")

    def _refresh_tables_list(self) -> None:
        super()._refresh_tables_list()
        self._refresh_onboarding_hints()

    def _on_tables_search_change(self, query: str) -> None:
        q = query.strip().lower()
        if q == "":
            return
        for idx, table in enumerate(self.project.tables):
            if q in table.table_name.lower():
                self.tables_list.selection_clear(0, tk.END)
                self.tables_list.selection_set(idx)
                self.tables_list.activate(idx)
                self.tables_list.see(idx)
                self._on_table_selected()
                return
        self.set_status(
            f"Tables search: no match for '{query.strip()}'. "
            "Fix: adjust the search text or clear the search."
        )

    def _on_columns_search_change(self, query: str) -> None:
        self._columns_filter_page_index = 0
        self._columns_filter_rows = self._filter_index_rows(self._columns_filter_index, query)
        self._render_columns_filter_page()

    def _on_fk_search_change(self, query: str) -> None:
        self._fk_filter_page_index = 0
        self._fk_filter_rows = self._filter_index_rows(self._fk_filter_index, query)
        self._render_fk_filter_page()

    @staticmethod
    def _filter_index_rows(rows: list[IndexedFilterRow], query: str) -> list[IndexedFilterRow]:
        q = query.strip().lower()
        if q == "":
            return list(rows)
        tokens = [token for token in q.split() if token]
        if not tokens:
            return list(rows)
        return [row for row in rows if all(token in row.search_text for token in tokens)]

    @staticmethod
    def _render_indexed_rows(tree: ttk.Treeview, rows: list[IndexedFilterRow]) -> None:
        for item in tree.get_children():
            tree.delete(item)
        for row in rows:
            tree.insert("", tk.END, values=row.values, tags=(str(row.source_index),))

    @staticmethod
    def _page_window(total_rows: int, page_index: int, page_size: int) -> tuple[int, int, int, int]:
        if total_rows <= 0:
            return 0, 0, 0, 0
        total_pages = (total_rows + page_size - 1) // page_size
        normalized_page = min(max(0, page_index), total_pages - 1)
        start = normalized_page * page_size
        end = min(total_rows, start + page_size)
        return start, end, total_pages, normalized_page

    def _render_columns_filter_page(self) -> None:
        start, end, total_pages, normalized_page = self._page_window(
            len(self._columns_filter_rows),
            self._columns_filter_page_index,
            FILTER_PAGE_SIZE,
        )
        self._columns_filter_page_index = normalized_page
        visible = self._columns_filter_rows[start:end]
        self._render_indexed_rows(self.columns_tree, visible)
        if not self._columns_filter_rows:
            self.columns_page_var.set("No matching columns.")
            self.columns_prev_btn.configure(state=tk.DISABLED)
            self.columns_next_btn.configure(state=tk.DISABLED)
            return
        self.columns_page_var.set(
            f"Rows {start + 1}-{end} of {len(self._columns_filter_rows)} "
            f"(page {normalized_page + 1}/{total_pages})"
        )
        self.columns_prev_btn.configure(state=(tk.NORMAL if normalized_page > 0 else tk.DISABLED))
        self.columns_next_btn.configure(
            state=(tk.NORMAL if normalized_page + 1 < total_pages else tk.DISABLED)
        )

    def _render_fk_filter_page(self) -> None:
        start, end, total_pages, normalized_page = self._page_window(
            len(self._fk_filter_rows),
            self._fk_filter_page_index,
            FILTER_PAGE_SIZE,
        )
        self._fk_filter_page_index = normalized_page
        visible = self._fk_filter_rows[start:end]
        self._render_indexed_rows(self.fks_tree, visible)
        if not self._fk_filter_rows:
            self.fks_page_var.set("No matching relationships.")
            self.fks_prev_btn.configure(state=tk.DISABLED)
            self.fks_next_btn.configure(state=tk.DISABLED)
            return
        self.fks_page_var.set(
            f"Rows {start + 1}-{end} of {len(self._fk_filter_rows)} "
            f"(page {normalized_page + 1}/{total_pages})"
        )
        self.fks_prev_btn.configure(state=(tk.NORMAL if normalized_page > 0 else tk.DISABLED))
        self.fks_next_btn.configure(
            state=(tk.NORMAL if normalized_page + 1 < total_pages else tk.DISABLED)
        )

    def _on_columns_filter_prev_page(self) -> None:
        if not self._columns_filter_rows:
            return
        self._columns_filter_page_index -= 1
        self._render_columns_filter_page()

    def _on_columns_filter_next_page(self) -> None:
        if not self._columns_filter_rows:
            return
        self._columns_filter_page_index += 1
        self._render_columns_filter_page()

    def _on_fk_filter_prev_page(self) -> None:
        if not self._fk_filter_rows:
            return
        self._fk_filter_page_index -= 1
        self._render_fk_filter_page()

    def _on_fk_filter_next_page(self) -> None:
        if not self._fk_filter_rows:
            return
        self._fk_filter_page_index += 1
        self._render_fk_filter_page()

    def _show_column_source_index(self, source_index: int) -> None:
        for pos, row in enumerate(self._columns_filter_rows):
            if row.source_index != source_index:
                continue
            self._columns_filter_page_index = pos // FILTER_PAGE_SIZE
            self._render_columns_filter_page()
            for item in self.columns_tree.get_children():
                tags = self.columns_tree.item(item, "tags")
                if tags and str(tags[0]) == str(source_index):
                    self.columns_tree.selection_set(item)
                    self.columns_tree.focus(item)
                    self.columns_tree.see(item)
                    return
            return

    def _show_fk_source_index(self, source_index: int) -> None:
        for pos, row in enumerate(self._fk_filter_rows):
            if row.source_index != source_index:
                continue
            self._fk_filter_page_index = pos // FILTER_PAGE_SIZE
            self._render_fk_filter_page()
            for item in self.fks_tree.get_children():
                tags = self.fks_tree.item(item, "tags")
                if tags and str(tags[0]) == str(source_index):
                    self.fks_tree.selection_set(item)
                    self.fks_tree.focus(item)
                    self.fks_tree.see(item)
                    return
            return

    def _refresh_columns_tree(self) -> None:
        self._columns_filter_index = []
        if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
            table = self.project.tables[self.selected_table_index]
            for idx, col in enumerate(table.columns):
                values = (
                    col.name,
                    col.dtype,
                    col.nullable,
                    col.primary_key,
                    col.unique,
                    col.min_value,
                    col.max_value,
                    ", ".join(col.choices) if col.choices else "",
                    col.pattern or "",
                )
                search_text = " ".join(str(v).lower() for v in (values[0], values[1], values[5], values[6], values[7], values[8]))
                self._columns_filter_index.append(
                    IndexedFilterRow(
                        source_index=idx,
                        values=values,
                        search_text=search_text,
                    )
                )
        query = self.columns_search.query_var.get() if hasattr(self, "columns_search") else ""
        self._columns_filter_rows = self._filter_index_rows(self._columns_filter_index, query)
        self._columns_filter_page_index = 0
        self._render_columns_filter_page()
        self._refresh_onboarding_hints()

    def _refresh_fks_tree(self) -> None:
        self._fk_filter_index = []
        for idx, fk in enumerate(self.project.foreign_keys):
            values = (fk.parent_table, fk.parent_column, fk.child_table, fk.child_column, fk.min_children, fk.max_children)
            search_text = " ".join(str(v).lower() for v in values)
            self._fk_filter_index.append(
                IndexedFilterRow(
                    source_index=idx,
                    values=values,
                    search_text=search_text,
                )
            )
        query = self.fk_search.query_var.get() if hasattr(self, "fk_search") else ""
        self._fk_filter_rows = self._filter_index_rows(self._fk_filter_index, query)
        self._fk_filter_page_index = 0
        self._render_fk_filter_page()
        self._refresh_onboarding_hints()

    def _on_fk_selection_changed(self, _event=None) -> None:
        self._sync_fk_defaults()

    def _on_preview_table_selected(self, _event=None) -> None:
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self.generated_rows:
            self._clear_preview_tree()
            self._refresh_onboarding_hints()
            return

        table = self.preview_table_var.get().strip()
        if not table or table not in self.generated_rows:
            self._clear_preview_tree()
            self._refresh_onboarding_hints()
            return

        try:
            limit = int(self.preview_limit_var.get().strip())
            if limit <= 0:
                raise ValueError
        except Exception:
            limit = 200
            self.preview_limit_var.set("200")

        self._preview_source_table = table
        self._preview_source_rows = list(self.generated_rows[table][:limit])
        self._refresh_preview_projection()
        self._refresh_onboarding_hints()

    def _clear_preview_tree(self) -> None:
        self._preview_source_table = ""
        self._preview_source_rows = []
        if hasattr(self, "preview_table"):
            self.preview_table.set_columns([])
            self.preview_table.set_rows([])
        self._refresh_onboarding_hints()

    def _set_table_editor_enabled(self, enabled: bool) -> None:
        super()._set_table_editor_enabled(enabled)
        if hasattr(self, "col_params_editor_btn"):
            self.col_params_editor_btn.configure(state=(tk.NORMAL if enabled else tk.DISABLED))

    def _apply_generator_params_template(self) -> None:
        before = self.col_params_var.get()
        super()._apply_generator_params_template()
        after = self.col_params_var.get()
        if after != before and after.strip() != "":
            self._show_toast("Applied generator params template.", level="success")

    def _move_column_up(self) -> None:
        self._move_selected_column(-1)

    def _move_column_down(self) -> None:
        self._move_selected_column(1)

    def _set_running(self, running: bool, msg: str) -> None:
        super()._set_running(running, msg)
        self._update_undo_redo_controls()
        self._refresh_onboarding_hints()

    def _set_project_io_running(self, running: bool, msg: str) -> None:
        self._project_io_running = bool(running)
        self.set_status(msg)
        self.set_busy(running)
        save_btn = getattr(self, "save_project_btn", None)
        load_btn = getattr(self, "load_project_btn", None)
        validate_btn = getattr(self, "run_validation_btn", None)
        state = tk.DISABLED if running else tk.NORMAL
        for widget in (save_btn, load_btn, validate_btn):
            if widget is not None:
                widget.configure(state=state)
        self._update_undo_redo_controls()
        self._refresh_onboarding_hints()

    def _project_io_busy(self) -> bool:
        return bool(self._project_io_running or self.project_io_lifecycle.state.is_running)

    def _project_io_guard(self, *, action: str) -> bool:
        if self.is_running:
            self.set_status(
                f"Cannot {action}: a generation/export run is currently active. "
                "Fix: wait for the current run to finish or cancel it first."
            )
            return False
        if self._project_io_busy():
            self.set_status(
                f"Cannot {action}: a project save/load operation is already running. "
                "Fix: wait for the current project operation to finish."
            )
            return False
        return True

    def _start_save_project_async(self) -> bool:
        if not self._project_io_guard(action="save project JSON"):
            return False
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            self._show_error_dialog("Save failed", str(exc))
            return False

        path = filedialog.asksaveasfilename(
            title="Save project as JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            self.set_status("Save project JSON cancelled.")
            return False

        project_snapshot = self.project
        started = self.project_io_lifecycle.run_async(
            worker=lambda: self._save_project_async_worker(project_snapshot, path),
            on_done=self._on_save_project_async_done,
            on_failed=lambda message: self._on_project_io_failed("Save failed", message),
            phase_label="Saving project JSON...",
            success_phase="Project save complete.",
            failure_phase="Project save failed.",
        )
        return bool(started)

    @staticmethod
    def _save_project_async_worker(project_snapshot, path: str) -> str:
        save_project_to_json(project_snapshot, path)
        return path

    def _on_save_project_async_done(self, payload: object) -> None:
        path = str(payload)
        self._mark_saved_baseline()
        self.set_status(f"Saved project: {path}")
        self._show_toast("Project saved.", level="success")

    def _start_load_project_async(self) -> None:
        if not self._project_io_guard(action="load project JSON"):
            return
        if not self.confirm_discard_or_save(action_name="loading another project"):
            return

        path = filedialog.askopenfilename(
            title="Load project JSON",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            self.set_status("Load project JSON cancelled.")
            return

        self.project_io_lifecycle.run_async(
            worker=lambda: self._load_project_async_worker(path),
            on_done=self._on_load_project_async_done,
            on_failed=lambda message: self._on_project_io_failed("Load failed", message),
            phase_label="Loading project JSON...",
            success_phase="Project load complete.",
            failure_phase="Project load failed.",
        )

    @staticmethod
    def _load_project_async_worker(path: str) -> tuple[str, object]:
        project = load_project_from_json(path)
        return path, project

    def _on_load_project_async_done(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._on_project_io_failed(
                "Load failed",
                "Load project JSON: invalid async payload. "
                "Fix: retry load and capture diagnostics if the issue repeats.",
            )
            return
        path, project = payload
        self._apply_loaded_project(project, str(path))

    def _apply_loaded_project(self, project: object, path: str) -> None:
        self._suspend_project_meta_dirty = True
        try:
            self.project = project
            self.project_name_var.set(self.project.name)
            self.seed_var.set(str(self.project.seed))
            self.project_timeline_constraints_var.set(
                json.dumps(self.project.timeline_constraints, sort_keys=True) if self.project.timeline_constraints else ""
            )
        finally:
            self._suspend_project_meta_dirty = False

        self.selected_table_index = None
        self._refresh_tables_list()
        self._refresh_columns_tree()
        self._set_table_editor_enabled(False)
        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()
        self.generated_rows = {}
        if hasattr(self, "preview_table_combo"):
            self.preview_table_combo.configure(values=())
        self.preview_table_var.set("")
        self._preview_column_preferences.clear()
        self._clear_preview_tree()
        self._reset_undo_history()
        self._run_validation_full()
        self.set_status(f"Loaded project: {path}")
        self._show_toast("Project loaded.", level="success")
        self._refresh_onboarding_hints()

    def _on_project_io_failed(self, title: str, message: str) -> None:
        self._show_error_dialog(title, str(message))

    def _save_project(self) -> bool:
        before_status = self.status_var.get()
        super()._save_project()
        after_status = self.status_var.get()
        saved = after_status != before_status and after_status.startswith("Saved project:")
        if saved:
            self._mark_saved_baseline()
            self._show_toast("Project saved.", level="success")
        return saved

    def _load_project(self) -> None:
        if not self.confirm_discard_or_save(action_name="loading another project"):
            return
        before_status = self.status_var.get()
        self._suspend_project_meta_dirty = True
        try:
            super()._load_project(confirm_unsaved=False)
        finally:
            self._suspend_project_meta_dirty = False
        after_status = self.status_var.get()
        loaded = after_status != before_status and after_status.startswith("Loaded project:")
        if loaded:
            self._reset_undo_history()
            self.generated_rows = {}
            if hasattr(self, "preview_table_combo"):
                self.preview_table_combo.configure(values=())
            self.preview_table_var.set("")
            self._preview_column_preferences.clear()
            self._refresh_inline_validation_summary()
            self._show_toast("Project loaded.", level="success")
            self._refresh_onboarding_hints()

    def _add_table(self) -> None:
        self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._add_table()
        self._record_undo_snapshot(
            before=before_state,
            label="Add table",
            reason="table changes",
        )

    def _remove_table(self) -> None:
        self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._remove_table()
        self._record_undo_snapshot(
            before=before_state,
            label="Remove table",
            reason="table changes",
        )

    def _apply_table_changes(self) -> None:
        staged_tables: set[str] = set()
        if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
            staged_tables.add(self.project.tables[self.selected_table_index].table_name)
        pending_name = self.table_name_var.get().strip()
        if pending_name:
            staged_tables.add(pending_name)
        if staged_tables:
            self._stage_incremental_validation(table_names=staged_tables)
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._apply_table_changes()
        self._record_undo_snapshot(
            before=before_state,
            label="Apply table changes",
            reason="table properties",
        )

    def _add_column(self) -> None:
        if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
            self._stage_incremental_validation(
                table_names=(self.project.tables[self.selected_table_index].table_name,),
            )
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._add_column()
        self._record_undo_snapshot(
            before=before_state,
            label="Add column",
            reason="column changes",
        )

    def _apply_selected_column_changes(self) -> None:
        if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
            self._stage_incremental_validation(
                table_names=(self.project.tables[self.selected_table_index].table_name,),
            )
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._apply_selected_column_changes()
        self._record_undo_snapshot(
            before=before_state,
            label="Edit column",
            reason="column changes",
        )

    def _remove_selected_column(self) -> None:
        if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
            self._stage_incremental_validation(
                table_names=(self.project.tables[self.selected_table_index].table_name,),
            )
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._remove_selected_column()
        self._record_undo_snapshot(
            before=before_state,
            label="Remove column",
            reason="column changes",
        )

    def _move_selected_column(self, delta: int) -> None:
        if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
            self._stage_incremental_validation(
                table_names=(self.project.tables[self.selected_table_index].table_name,),
            )
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._move_selected_column(delta)
        self._record_undo_snapshot(
            before=before_state,
            label=("Move column up" if delta < 0 else "Move column down"),
            reason="column order",
        )

    def _add_fk(self) -> None:
        parent = self.fk_parent_table_var.get().strip()
        child = self.fk_child_table_var.get().strip()
        staged = tuple(name for name in (parent, child) if name)
        if staged:
            self._stage_incremental_validation(table_names=staged)
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._add_fk()
        self._record_undo_snapshot(
            before=before_state,
            label="Add relationship",
            reason="relationship changes",
        )

    def _remove_selected_fk(self) -> None:
        staged_tables: set[str] = set()
        idx = self._selected_fk_index()
        if idx is not None and idx < len(self.project.foreign_keys):
            fk = self.project.foreign_keys[idx]
            staged_tables.add(fk.parent_table)
            staged_tables.add(fk.child_table)
        if staged_tables:
            self._stage_incremental_validation(table_names=staged_tables)
        else:
            self._stage_full_validation()
        before_state = self._capture_undo_snapshot()
        super()._remove_selected_fk()
        self._record_undo_snapshot(
            before=before_state,
            label="Remove relationship",
            reason="relationship changes",
        )

    def _on_generate_project(self) -> None:
        if self._project_io_busy():
            self.set_status(
                "Cannot generate: a project save/load operation is currently running. "
                "Fix: wait for project save/load to finish."
            )
            return
        if self.is_running:
            return
        self._run_validation_full()
        if self.last_validation_errors > 0:
            self._show_error_dialog(
                "Cannot generate",
                "Generate action: schema has validation errors. "
                "Fix: run validation and resolve all error cells first.",
            )
            return
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            self._show_error_dialog("Invalid project", str(exc))
            return

        self.job_lifecycle.run_async(
            worker=lambda: generate_project_rows(self.project),
            on_done=self._on_generated_ok,
            on_failed=self._on_job_failed,
            phase_label="Generating data for all tables...",
        )

    def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
        super()._on_generated_ok(rows)
        self._refresh_onboarding_hints()

    def _clear_generated(self) -> None:
        super()._clear_generated()
        self._refresh_onboarding_hints()

    def _on_export_csv(self) -> None:
        if self._project_io_busy():
            self.set_status(
                "Cannot export CSV: a project save/load operation is currently running. "
                "Fix: wait for project save/load to finish."
            )
            return
        if self.is_running:
            return
        if not self.generated_rows:
            super()._on_export_csv()
            return

        self._run_validation_full()
        if self.last_validation_errors > 0:
            self._show_error_dialog(
                "Cannot export",
                "CSV export action: schema has validation errors. "
                "Fix: run validation and resolve all error cells first.",
            )
            return
        super()._on_export_csv()

    def _on_create_insert_sqlite(self) -> None:
        if self._project_io_busy():
            self.set_status(
                "Cannot run SQLite export: a project save/load operation is currently running. "
                "Fix: wait for project save/load to finish."
            )
            return
        if self.is_running:
            return
        self._run_validation_full()
        if self.last_validation_errors > 0:
            self._show_error_dialog(
                "Cannot export",
                "SQLite export action: schema has validation errors. "
                "Fix: run validation and resolve all error cells first.",
            )
            return
        if not self.generated_rows:
            self._show_warning_dialog("No data", "Generate data first.")
            return

        db_path = self.db_path_var.get().strip()
        if not db_path:
            self._show_error_dialog(
                "Missing DB path",
                "Generate / Preview / Export / SQLite panel: SQLite DB path is required. "
                "Fix: choose a SQLite database file path.",
            )
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            self._show_error_dialog("Invalid project", str(exc))
            return

        def _sqlite_job() -> dict[str, int]:
            create_tables(db_path, self.project)
            return insert_project_rows(db_path, self.project, self.generated_rows, chunk_size=5000)

        self.job_lifecycle.run_async(
            worker=_sqlite_job,
            on_done=lambda counts: self._on_sqlite_ok(db_path, counts),
            on_failed=self._on_job_failed,
            phase_label="Creating tables and inserting rows into SQLite...",
        )

    def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
        super()._on_sqlite_ok(db_path, counts)

    def _on_generate_sample(self) -> None:
        if self._project_io_busy():
            self.set_status(
                "Cannot generate sample: a project save/load operation is currently running. "
                "Fix: wait for project save/load to finish."
            )
            return
        if self.is_running:
            return

        self._run_validation_full()
        if self.last_validation_errors > 0:
            self._show_error_dialog(
                "Cannot generate",
                "Generate sample action: schema has validation errors. "
                "Fix: run validation and resolve all error cells first.",
            )
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            self._show_error_dialog("Invalid project", str(exc))
            return

        sample_project = self._make_sample_project(10)
        self.job_lifecycle.run_async(
            worker=lambda: generate_project_rows(sample_project),
            on_done=self._on_generated_ok,
            on_failed=self._on_job_failed,
            phase_label="Generating sample data (10 rows per root table)...",
        )
