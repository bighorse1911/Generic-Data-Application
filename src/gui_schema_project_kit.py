import tkinter as tk
from tkinter import ttk

from src.generator_project import generate_project_rows
from src.gui_kit.column_chooser import ColumnChooserDialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.forms import FormBuilder
from src.gui_kit.job_lifecycle import JobLifecycleController
from src.gui_kit.json_editor import JsonEditorDialog
from src.gui_kit.layout import BaseScreen
from src.gui_kit.panels import CollapsiblePanel, Tabs
from src.gui_kit.search import SearchEntry
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.scroll import ScrollFrame
from src.gui_kit.table import TableView
from src.gui_kit.tokens import TokenEntry
from src.gui_kit.validation import InlineValidationEntry, InlineValidationSummary
from src.schema_project_model import validate_project
from src.gui_schema_project import (
    DTYPES,
    EXPORT_OPTIONS,
    GENERATORS,
    PATTERN_PRESETS,
    SCD_MODES,
    SchemaProjectDesignerScreen,
    ValidationIssue,
    ValidationHeatmap,
)
from src.storage_sqlite_project import create_tables, insert_project_rows


class SchemaProjectDesignerKitScreen(SchemaProjectDesignerScreen, BaseScreen):
    """
    Layout-only refactor of SchemaProjectDesignerScreen using reusable gui_kit
    components. Business logic and callbacks are inherited unchanged.
    """

    def _build(self) -> None:
        if hasattr(self, "scroll"):
            self.scroll.destroy()

        self.scroll = ScrollFrame(self, padding=16)
        self.scroll.pack(fill="both", expand=True)
        self._root_content = self.scroll.content
        self.toast_center = ToastCenter(self)
        self.shortcut_manager = ShortcutManager(self)
        self._preview_source_table = ""
        self._preview_source_rows: list[dict[str, object]] = []
        self._preview_column_preferences: dict[str, list[str]] = {}

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
        self._register_shortcuts()
        self._suspend_project_meta_dirty = False
        self.project_name_var.trace_add("write", self._on_project_meta_changed)
        self.seed_var.trace_add("write", self._on_project_meta_changed)
        self.enable_dirty_state_guard(context="Schema Project Designer", on_save=self._save_project)
        self.mark_clean()
        self.job_lifecycle = JobLifecycleController(
            set_running=self._set_running,
            run_async=self._run_job_async,
        )

        # Keep default platform theme; dark mode is intentionally disabled.
        self.kit_dark_mode_enabled = False

    def _run_job_async(self, worker, on_done, on_failed) -> None:
        self.safe_threaded_job(worker, on_done, on_failed)

    def build_header(self) -> ttk.Frame:
        header = BaseScreen.build_header(
            self,
            self._root_content,
            title="Schema Project Designer (Kit Preview)",
            back_command=self._on_back_requested,
        )
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

        buttons = ttk.Frame(project_box)
        buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Save project JSON", command=self._save_project).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(buttons, text="Load project JSON", command=self._load_project).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        validation_box = ttk.LabelFrame(panel.body, text="Schema validation", padding=10)
        validation_box.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        validation_box.columnconfigure(0, weight=1)
        validation_box.rowconfigure(1, weight=1)
        validation_box.rowconfigure(2, weight=0)

        validation_top = ttk.Frame(validation_box)
        validation_top.grid(row=0, column=0, sticky="ew")
        validation_top.columnconfigure(1, weight=1)

        ttk.Button(validation_top, text="Run validation", command=self._run_validation).grid(row=0, column=0, sticky="w")
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

        self.apply_table_btn = ttk.Button(right_box, text="Apply table changes", command=self._apply_table_changes)
        self.apply_table_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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

        column_actions = ttk.Frame(columns_box)
        column_actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
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

        self.remove_fk_btn = ttk.Button(list_box, text="Remove selected relationship", command=self._remove_selected_fk)
        self.remove_fk_btn.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        return panel

    def build_generate_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.generate_tab, "Generate / Preview / Export / SQLite", collapsed=False)
        panel.pack(fill="both", expand=True)
        self.generate_panel = panel

        panel.body.columnconfigure(0, weight=1)
        panel.body.rowconfigure(2, weight=1)

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

        preview_box = ttk.LabelFrame(panel.body, text="Preview", padding=8)
        preview_box.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
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
        self.preview_table.enable_pagination(page_size=100)
        self.preview_tree = self.preview_table.tree
        return panel

    def build_status_bar(self) -> ttk.Frame:
        return BaseScreen.build_status_bar(self, self._root_content, include_progress=False)

    def _on_back_requested(self) -> None:
        if self.confirm_discard_or_save(action_name="returning to Home"):
            self.app.go_home()

    def _refresh_inline_validation_summary(self) -> None:
        if not hasattr(self, "inline_validation"):
            return

        entries: list[InlineValidationEntry] = []
        issues = self._validate_project_detailed(self.project)
        for issue in issues:
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
                for item in self.columns_tree.get_children():
                    values = self.columns_tree.item(item, "values")
                    if len(values) > 0 and str(values[0]) == column_name:
                        self.columns_tree.selection_set(item)
                        self.columns_tree.focus(item)
                        self.columns_tree.see(item)
                        self._on_column_selected()
                        break
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
        for item in self.fks_tree.get_children():
            values = self.fks_tree.item(item, "values")
            if len(values) < 4:
                continue
            table_value = str(values[2])
            column_value = str(values[3])
            if table_value != child_table:
                continue
            if child_column is not None and column_value != child_column:
                continue
            self.fks_tree.selection_set(item)
            self.fks_tree.focus(item)
            self.fks_tree.see(item)
            self.set_status(
                f"Jumped to validation location: FK '{table_value}.{column_value}'."
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
        self._show_toast("Applied preview column visibility/order.", level="success")

    def _mark_dirty_if_project_changed(self, before_project, *, reason: str) -> None:
        if self.project != before_project:
            self.mark_dirty(reason)

    def _on_project_meta_changed(self, *_args) -> None:
        if getattr(self, "_suspend_project_meta_dirty", False):
            return
        self.mark_dirty("project settings")

    def _register_shortcuts(self) -> None:
        self.shortcut_manager.register("<Control-s>", "Save project JSON", self._save_project)
        self.shortcut_manager.register("<Control-o>", "Load project JSON", self._load_project)
        self.shortcut_manager.register("<Control-f>", "Focus table search", self._focus_table_search)
        self.shortcut_manager.register("<F5>", "Run validation", self._run_validation)
        self.shortcut_manager.register("<Control-Return>", "Generate data", self._on_generate_project)
        self.shortcut_manager.register("<F1>", "Open shortcuts help", self._show_shortcuts_help)

    def _run_validation(self) -> None:
        super()._run_validation()
        self._refresh_inline_validation_summary()

    def _focus_table_search(self) -> None:
        if hasattr(self, "tables_search"):
            self.tables_search.focus()

    def _show_shortcuts_help(self) -> None:
        self.shortcut_manager.show_help_dialog(title="Schema Project Shortcuts")

    def _show_toast(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
        if hasattr(self, "toast_center"):
            self.toast_center.show_toast(message, level=level, duration_ms=duration_ms)

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
        self._apply_tree_filter(self.columns_tree, query, key_columns=(0, 1, 7, 8))

    def _on_fk_search_change(self, query: str) -> None:
        self._apply_tree_filter(self.fks_tree, query, key_columns=(0, 2, 3))

    def _apply_tree_filter(self, tree: ttk.Treeview, query: str, *, key_columns: tuple[int, ...]) -> None:
        q = query.strip().lower()
        all_items = list(tree.get_children(""))
        for item in all_items:
            tree.detach(item)
        if q == "":
            for item in all_items:
                tree.reattach(item, "", tk.END)
            return

        for item in all_items:
            if not tree.exists(item):
                continue
            values = tree.item(item, "values")
            haystack = " ".join(str(values[idx]) for idx in key_columns if idx < len(values)).lower()
            if q in haystack:
                tree.reattach(item, "", tk.END)

    def _refresh_columns_tree(self) -> None:
        super()._refresh_columns_tree()
        if hasattr(self, "columns_search"):
            self._on_columns_search_change(self.columns_search.query_var.get())

    def _refresh_fks_tree(self) -> None:
        super()._refresh_fks_tree()
        if hasattr(self, "fk_search"):
            self._on_fk_search_change(self.fk_search.query_var.get())

    def _on_fk_selection_changed(self, _event=None) -> None:
        self._sync_fk_defaults()

    def _on_preview_table_selected(self, _event=None) -> None:
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self.generated_rows:
            self._clear_preview_tree()
            return

        table = self.preview_table_var.get().strip()
        if not table or table not in self.generated_rows:
            self._clear_preview_tree()
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

    def _clear_preview_tree(self) -> None:
        self._preview_source_table = ""
        self._preview_source_rows = []
        if hasattr(self, "preview_table"):
            self.preview_table.set_columns([])
            self.preview_table.set_rows([])

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

    def _save_project(self) -> bool:
        before_status = self.status_var.get()
        super()._save_project()
        after_status = self.status_var.get()
        saved = after_status != before_status and after_status.startswith("Saved project:")
        if saved:
            self.mark_clean()
            self._show_toast("Project saved.", level="success")
        return saved

    def _load_project(self) -> None:
        if not self.confirm_discard_or_save(action_name="loading another project"):
            return
        before_status = self.status_var.get()
        self._suspend_project_meta_dirty = True
        try:
            super()._load_project()
        finally:
            self._suspend_project_meta_dirty = False
        after_status = self.status_var.get()
        loaded = after_status != before_status and after_status.startswith("Loaded project:")
        if loaded:
            self.mark_clean()
            self._preview_column_preferences.clear()
            self._refresh_inline_validation_summary()
            self._show_toast("Project loaded.", level="success")

    def _add_table(self) -> None:
        before = self.project
        super()._add_table()
        self._mark_dirty_if_project_changed(before, reason="table changes")

    def _remove_table(self) -> None:
        before = self.project
        super()._remove_table()
        self._mark_dirty_if_project_changed(before, reason="table changes")

    def _apply_table_changes(self) -> None:
        before = self.project
        super()._apply_table_changes()
        self._mark_dirty_if_project_changed(before, reason="table properties")

    def _add_column(self) -> None:
        before = self.project
        super()._add_column()
        self._mark_dirty_if_project_changed(before, reason="column changes")

    def _apply_selected_column_changes(self) -> None:
        before = self.project
        super()._apply_selected_column_changes()
        self._mark_dirty_if_project_changed(before, reason="column changes")

    def _remove_selected_column(self) -> None:
        before = self.project
        super()._remove_selected_column()
        self._mark_dirty_if_project_changed(before, reason="column changes")

    def _move_selected_column(self, delta: int) -> None:
        before = self.project
        super()._move_selected_column(delta)
        self._mark_dirty_if_project_changed(before, reason="column order")

    def _add_fk(self) -> None:
        before = self.project
        super()._add_fk()
        self._mark_dirty_if_project_changed(before, reason="relationship changes")

    def _remove_selected_fk(self) -> None:
        before = self.project
        super()._remove_selected_fk()
        self._mark_dirty_if_project_changed(before, reason="relationship changes")

    def _on_generate_project(self) -> None:
        if self.is_running:
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
        total_rows = sum(len(v) for v in rows.values())
        self._show_toast(f"Generated {total_rows} rows.", level="success")

    def _on_create_insert_sqlite(self) -> None:
        if self.is_running:
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
        total_inserted = sum(counts.values())
        self._show_toast(
            f"SQLite insert complete ({total_inserted} rows) at {db_path}.",
            level="success",
            duration_ms=3500,
        )

    def _on_generate_sample(self) -> None:
        if self.is_running:
            return

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
