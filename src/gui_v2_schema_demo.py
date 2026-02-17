from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.generator_project import generate_project_rows
from src.gui_kit.accessibility import FocusController
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.forms import FormBuilder
from src.gui_kit.job_lifecycle import JobLifecycleController
from src.gui_kit.json_editor import JsonEditorDialog
from src.gui_kit.panels import CollapsiblePanel
from src.gui_kit.scroll import ScrollFrame
from src.gui_kit.search import SearchEntry
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.table import TableView
from src.gui_kit.tokens import TokenEntry
from src.gui_kit.validation import InlineValidationEntry
from src.gui_kit.validation import InlineValidationSummary
from src.gui_route_policy import SCHEMA_PRIMARY_ROUTE
from src.gui_schema_project import DTYPES
from src.gui_schema_project import EXPORT_OPTIONS
from src.gui_schema_project import GENERATORS
from src.gui_schema_project import PATTERN_PRESETS
from src.gui_schema_project import SCD_MODES
from src.gui_schema_project import ValidationHeatmap
from src.gui_schema_project import ValidationIssue
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen
from src.schema_project_model import ColumnSpec
from src.schema_project_model import ForeignKeySpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec

V2_DEMO_BG = "#f4efe6"
V2_DEMO_PANEL = "#fbf8f1"
V2_DEMO_HEADER = "#0f2138"
V2_DEMO_ACTION = "#c76d2a"


class SchemaDemoV2Screen(SchemaProjectDesignerKitScreen):
    """Mockup-inspired v2 schema editor route with model-backed behavior."""

    ERROR_SURFACE_CONTEXT = "Schema demo v2"
    ERROR_DIALOG_TITLE = "Schema demo v2 error"
    WARNING_DIALOG_TITLE = "Schema demo v2 warning"

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        self._demo_seeded = False
        self._suspend_project_meta_dirty = False
        super().__init__(parent, app, cfg)

    def _build(self) -> None:
        if hasattr(self, "scroll"):
            self.scroll.destroy()

        self.scroll = ScrollFrame(self, padding=12)
        self.scroll.pack(fill="both", expand=True)
        self._root_content = self.scroll.content
        self.toast_center = ToastCenter(self)
        self.shortcut_manager = ShortcutManager(self)
        self.focus_controller = FocusController(self)
        self._preview_source_table = ""
        self._preview_source_rows = []
        self._preview_column_preferences: dict[str, list[str]] = {}

        self._build_header()
        self._build_main_body()
        self._build_bottom_actions()
        self._build_status_bar()

        self._register_focus_anchors()
        self._register_shortcuts()
        self.enable_dirty_state_guard(context="Schema Demo v2", on_save=self._save_project)
        self.mark_clean()
        self.job_lifecycle = JobLifecycleController(
            set_running=self._set_running,
            run_async=self._run_job_async,
        )
        self.kit_dark_mode_enabled = False

    def on_show(self) -> None:
        if not self._demo_seeded:
            self._seed_demo_project()
            self._demo_seeded = True
        super().on_show()

    def _build_header(self) -> None:
        header = tk.Frame(self._root_content, bg=V2_DEMO_HEADER, height=54)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        tk.Button(
            header,
            text="Back",
            command=self._on_back_requested,
            bg="#d9d2c4",
            fg="#1f1f1f",
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="left", padx=(8, 8), pady=8)

        tk.Label(
            header,
            text="Schema Demo v2",
            bg=V2_DEMO_HEADER,
            fg="#f5f5f5",
            font=("Cambria", 16, "bold"),
        ).pack(side="left", pady=8)

        tk.Label(
            header,
            textvariable=self._dirty_indicator_var,
            bg=V2_DEMO_HEADER,
            fg="#f5f5f5",
            font=("Calibri", 10, "bold"),
        ).pack(side="left", padx=(10, 0), pady=8)

        tk.Button(
            header,
            text="Open Classic",
            command=lambda: self.app.show_screen(SCHEMA_PRIMARY_ROUTE),
            bg="#d9d2c4",
            fg="#1f1f1f",
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="right", padx=(0, 8), pady=8)
        tk.Button(
            header,
            text="Shortcuts",
            command=self._show_shortcuts_help,
            bg="#d9d2c4",
            fg="#1f1f1f",
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="right", padx=(0, 8), pady=8)

    def _build_main_body(self) -> None:
        body = tk.Frame(self._root_content, bg=V2_DEMO_BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=230)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_tables_panel(body)
        self._build_right_content(body)

    def _build_tables_panel(self, parent: tk.Widget) -> None:
        left = tk.Frame(parent, bg=V2_DEMO_PANEL, bd=1, relief="solid")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)

        tk.Label(
            left,
            text="Tables",
            bg=V2_DEMO_PANEL,
            fg="#1f1f1f",
            anchor="w",
            font=("Cambria", 14, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        self.tables_search = SearchEntry(left, on_change=self._on_tables_search_change, delay_ms=150)
        self.tables_search.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

        table_buttons = tk.Frame(left, bg=V2_DEMO_PANEL)
        table_buttons.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        table_buttons.columnconfigure(0, weight=1)
        table_buttons.columnconfigure(1, weight=1)
        tk.Button(
            table_buttons,
            text="+ Add Table",
            command=self._add_table,
            bg="#ece8de",
            fg="#202020",
            relief="groove",
            padx=8,
            pady=4,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Button(
            table_buttons,
            text="Remove",
            command=self._remove_table,
            bg="#ece8de",
            fg="#202020",
            relief="groove",
            padx=8,
            pady=4,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        list_host = tk.Frame(left, bg=V2_DEMO_PANEL)
        list_host.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_host.columnconfigure(0, weight=1)
        list_host.rowconfigure(0, weight=1)

        self.tables_list = tk.Listbox(list_host, height=14, exportselection=False)
        self.tables_list.grid(row=0, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(list_host, orient="vertical", command=self.tables_list.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        self.tables_list.configure(yscrollcommand=table_scroll.set)
        self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

    def _build_right_content(self, parent: tk.Widget) -> None:
        right = tk.Frame(parent, bg=V2_DEMO_BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self._build_table_details(right)
        self._build_data_preview(right)

    def _build_table_details(self, parent: tk.Widget) -> None:
        details_box = tk.LabelFrame(
            parent,
            text="Table Details",
            bg=V2_DEMO_PANEL,
            fg="#1f1f1f",
            padx=8,
            pady=8,
            font=("Cambria", 12, "bold"),
        )
        details_box.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        details_box.columnconfigure(0, weight=1)
        details_box.rowconfigure(0, weight=1)

        self.details_tabs = ttk.Notebook(details_box)
        self.details_tabs.grid(row=0, column=0, sticky="nsew")
        self.columns_tab = ttk.Frame(self.details_tabs, padding=8)
        self.constraints_tab = ttk.Frame(self.details_tabs, padding=8)
        self.relationships_tab = ttk.Frame(self.details_tabs, padding=8)
        self.details_tabs.add(self.columns_tab, text="Columns")
        self.details_tabs.add(self.constraints_tab, text="Constraints")
        self.details_tabs.add(self.relationships_tab, text="Relationships")
        self._tab_by_key = {
            "columns": self.columns_tab,
            "constraints": self.constraints_tab,
            "relationships": self.relationships_tab,
        }

        self._build_columns_tab()
        self._build_constraints_tab()
        self._build_relationships_tab()

    def _build_columns_tab(self) -> None:
        self.columns_tab.columnconfigure(0, weight=1)
        self.columns_tab.rowconfigure(2, weight=1)

        self._selected_table_title_var = tk.StringVar(value="No table selected")
        tk.Label(
            self.columns_tab,
            textvariable=self._selected_table_title_var,
            anchor="w",
            font=("Cambria", 13, "bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.columns_search = SearchEntry(self.columns_tab, on_change=self._on_columns_search_change, delay_ms=150)
        self.columns_search.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        columns_grid = tk.Frame(self.columns_tab)
        columns_grid.grid(row=2, column=0, sticky="nsew")
        columns_grid.columnconfigure(0, weight=1)
        columns_grid.rowconfigure(0, weight=1)

        self.columns_table = TableView(columns_grid, height=7)
        self.columns_table.grid(row=0, column=0, sticky="nsew")
        self.columns_table.set_columns(["Column Name", "Data Type", "Nullable", "Default Value"])
        self.columns_tree = self.columns_table.tree
        self.columns_tree.column("Column Name", width=180)
        self.columns_tree.column("Data Type", width=110)
        self.columns_tree.column("Nullable", width=90, anchor="center")
        self.columns_tree.column("Default Value", width=190)
        self.columns_tree.bind("<<TreeviewSelect>>", self._on_column_selected)

        editor = ttk.LabelFrame(self.columns_tab, text="Column editor", padding=8)
        editor.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        editor.columnconfigure(0, weight=1)

        form_host = ttk.Frame(editor)
        form_host.grid(row=0, column=0, sticky="ew")
        form = FormBuilder(form_host)
        self.col_name_entry = form.add_entry("Column name", self.col_name_var)
        self.col_dtype_combo = form.add_combo("Data type", self.col_dtype_var, DTYPES, readonly=True)
        self.col_min_entry = form.add_entry("Min value", self.col_min_var, width=12)
        self.col_max_entry = form.add_entry("Max value", self.col_max_var, width=12)
        self.col_choices_entry = form.add_entry("Choices (comma-separated)", self.col_choices_var)
        self.col_pattern_entry = form.add_entry("Regex pattern", self.col_pattern_var)
        self.col_pattern_entry.bind("<FocusOut>", self._on_pattern_entry_focus_out)
        self.col_pattern_preset_combo = form.add_combo(
            "Pattern preset",
            self.col_pattern_preset_var,
            list(PATTERN_PRESETS.keys()),
            readonly=True,
        )
        self.col_pattern_preset_combo.bind("<<ComboboxSelected>>", self._on_pattern_preset_selected)
        self.col_generator_combo = form.add_combo("Generator", self.col_generator_var, GENERATORS, readonly=True)
        self.col_params_entry = form.add_entry("Generator params JSON", self.col_params_var)
        self.col_depends_entry = form.add_entry("Depends on column(s)", self.col_depends_var)

        checks = ttk.Frame(editor)
        checks.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.col_nullable_chk = ttk.Checkbutton(checks, text="Nullable", variable=self.col_nullable_var)
        self.col_nullable_chk.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.col_pk_chk = ttk.Checkbutton(checks, text="Primary key", variable=self.col_pk_var)
        self.col_pk_chk.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.col_unique_chk = ttk.Checkbutton(checks, text="Unique", variable=self.col_unique_var)
        self.col_unique_chk.grid(row=0, column=2, sticky="w")

        action_row = ttk.Frame(editor)
        action_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        action_row.columnconfigure(0, weight=1)
        action_row.columnconfigure(1, weight=1)
        action_row.columnconfigure(2, weight=1)
        action_row.columnconfigure(3, weight=1)
        action_row.columnconfigure(4, weight=1)
        self.add_col_btn = ttk.Button(action_row, text="Add Column", command=self._add_column)
        self.add_col_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(action_row, text="Remove Column", command=self._remove_selected_column).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=4,
        )
        self.edit_col_btn = ttk.Button(action_row, text="Apply Edits", command=self._apply_selected_column_changes)
        self.edit_col_btn.grid(row=0, column=2, sticky="ew", padx=4)
        self.mock_rules_btn = ttk.Button(action_row, text="Mock Data Rules", command=self._open_mock_data_rules)
        self.mock_rules_btn.grid(row=0, column=3, sticky="ew", padx=4)
        self.distribution_btn = ttk.Button(
            action_row,
            text="Distribution Config",
            command=self._open_distribution_config,
        )
        self.distribution_btn.grid(row=0, column=4, sticky="ew", padx=(4, 0))

        template_row = ttk.Frame(editor)
        template_row.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        template_row.columnconfigure(0, weight=1)
        template_row.columnconfigure(1, weight=1)
        template_row.columnconfigure(2, weight=1)
        self.col_params_template_btn = ttk.Button(
            template_row,
            text="Fill params template",
            command=self._apply_generator_params_template,
        )
        self.col_params_template_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.col_params_editor_btn = ttk.Button(
            template_row,
            text="Open params JSON editor",
            command=self._open_params_json_editor,
        )
        self.col_params_editor_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.preview_columns_btn = ttk.Button(
            template_row,
            text="Choose Preview Columns",
            command=self._open_preview_column_chooser,
        )
        self.preview_columns_btn.grid(
            row=0,
            column=2,
            sticky="ew",
            padx=(4, 0),
        )

    def _build_constraints_tab(self) -> None:
        self.constraints_tab.columnconfigure(0, weight=1)
        self.constraints_tab.rowconfigure(0, weight=1)
        constraints_body = ttk.Frame(self.constraints_tab)
        constraints_body.grid(row=0, column=0, sticky="nsew")
        constraints_body.columnconfigure(0, weight=1)

        self.constraints_rules_panel = CollapsiblePanel(
            constraints_body,
            "Project + Table Rules",
            collapsed=False,
        )
        self.constraints_rules_panel.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.constraints_rules_panel.body.columnconfigure(0, weight=1)

        project_box = ttk.LabelFrame(self.constraints_rules_panel.body, text="Project settings", padding=8)
        project_box.grid(row=0, column=0, sticky="ew")
        project_form_host = ttk.Frame(project_box)
        project_form_host.pack(fill="x")
        project_form = FormBuilder(project_form_host)
        self.project_name_entry = project_form.add_entry("Project name", self.project_name_var)
        self.seed_entry = project_form.add_entry("Seed", self.seed_var, width=12)
        save_load = ttk.Frame(project_box)
        save_load.pack(fill="x", pady=(8, 0))
        save_load.columnconfigure(0, weight=1)
        save_load.columnconfigure(1, weight=1)
        ttk.Button(save_load, text="Save project JSON", command=self._save_project).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(save_load, text="Load project JSON", command=self._load_project).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        table_box = ttk.LabelFrame(self.constraints_rules_panel.body, text="Table constraints", padding=8)
        table_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        table_form_host = ttk.Frame(table_box)
        table_form_host.pack(fill="x")
        table_form = FormBuilder(table_form_host)
        self.table_name_entry = table_form.add_entry("Table name", self.table_name_var)
        self.row_count_entry = table_form.add_entry("Root row count", self.row_count_var, width=12)
        self.table_business_key_unique_count_entry = table_form.add_entry(
            "Unique business keys (optional)",
            self.table_business_key_unique_count_var,
            width=12,
        )
        self.table_business_key_entry = TokenEntry(table_form_host, textvariable=self.table_business_key_var)
        table_form.add_widget("Business key columns", self.table_business_key_entry)
        self.table_business_key_static_entry = TokenEntry(
            table_form_host,
            textvariable=self.table_business_key_static_columns_var,
        )
        table_form.add_widget("Business key static columns", self.table_business_key_static_entry)
        self.table_business_key_changing_entry = TokenEntry(
            table_form_host,
            textvariable=self.table_business_key_changing_columns_var,
        )
        table_form.add_widget("Business key changing columns", self.table_business_key_changing_entry)
        self.table_scd_mode_combo = table_form.add_combo("SCD mode", self.table_scd_mode_var, SCD_MODES, readonly=True)
        self.table_scd_tracked_entry = TokenEntry(table_form_host, textvariable=self.table_scd_tracked_columns_var)
        table_form.add_widget("SCD tracked columns", self.table_scd_tracked_entry)
        self.table_scd_active_from_entry = table_form.add_entry("SCD active from column", self.table_scd_active_from_var)
        self.table_scd_active_to_entry = table_form.add_entry("SCD active to column", self.table_scd_active_to_var)
        self.apply_table_btn = ttk.Button(table_box, text="Apply table changes", command=self._apply_table_changes)
        self.apply_table_btn.pack(fill="x", pady=(8, 0))

        self.constraints_distribution_panel = CollapsiblePanel(
            constraints_body,
            "Output + Distribution Config",
            collapsed=False,
        )
        self.constraints_distribution_panel.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.constraints_distribution_panel.body.columnconfigure(1, weight=1)
        ttk.Label(self.constraints_distribution_panel.body, text="SQLite DB path:").grid(row=0, column=0, sticky="w", pady=2, padx=(0, 8))
        self.db_path_entry = ttk.Entry(self.constraints_distribution_panel.body, textvariable=self.db_path_var)
        self.db_path_entry.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Button(self.constraints_distribution_panel.body, text="Browse...", command=self._browse_db_path).grid(
            row=0,
            column=2,
            sticky="ew",
            pady=2,
            padx=(8, 0),
        )
        ttk.Label(self.constraints_distribution_panel.body, text="Export format:").grid(row=1, column=0, sticky="w", pady=2, padx=(0, 8))
        self.export_option_combo = ttk.Combobox(
            self.constraints_distribution_panel.body,
            values=EXPORT_OPTIONS,
            textvariable=self.export_option_var,
            state="readonly",
        )
        self.export_option_combo.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(
            self.constraints_distribution_panel.body,
            text="Export data",
            command=self._on_export_data,
        ).grid(row=1, column=2, sticky="ew", pady=2, padx=(8, 0))

        ttk.Label(self.constraints_distribution_panel.body, text="Preview table:").grid(row=2, column=0, sticky="w", pady=2, padx=(0, 8))
        self.preview_table_combo = ttk.Combobox(
            self.constraints_distribution_panel.body,
            textvariable=self.preview_table_var,
            state="readonly",
        )
        self.preview_table_combo.grid(row=2, column=1, sticky="ew", pady=2)
        self.preview_table_combo.bind("<<ComboboxSelected>>", self._on_preview_table_selected)
        ttk.Button(
            self.constraints_distribution_panel.body,
            text="Refresh Preview",
            command=self._refresh_preview,
        ).grid(row=2, column=2, sticky="ew", pady=2, padx=(8, 0))

        self.preview_limit_var = tk.StringVar(value="200")
        ttk.Label(self.constraints_distribution_panel.body, text="Preview row limit:").grid(row=3, column=0, sticky="w", pady=2, padx=(0, 8))
        ttk.Entry(self.constraints_distribution_panel.body, textvariable=self.preview_limit_var, width=12).grid(
            row=3,
            column=1,
            sticky="w",
            pady=2,
        )
        self.preview_paging_chk = ttk.Checkbutton(
            self.constraints_distribution_panel.body,
            text="Enable pagination",
            variable=self.preview_paging_enabled_var,
            command=self._on_preview_paging_toggled,
        )
        self.preview_paging_chk.grid(row=4, column=0, sticky="w", pady=(6, 2))
        self.preview_page_size_combo = ttk.Combobox(
            self.constraints_distribution_panel.body,
            textvariable=self.preview_page_size_var,
            values=["50", "100", "200", "500"],
            state="readonly",
            width=8,
        )
        self.preview_page_size_combo.grid(row=4, column=1, sticky="w", pady=(6, 2))
        self.preview_page_size_combo.bind("<<ComboboxSelected>>", self._on_preview_page_size_changed)

        actions = ttk.Frame(self.constraints_distribution_panel.body)
        actions.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        self.sample_btn = ttk.Button(actions, text="Generate sample", command=self._on_generate_sample)
        self.sample_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.export_btn = ttk.Button(actions, text="Run SQLite Insert", command=self._on_create_insert_sqlite)
        self.export_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.clear_btn = ttk.Button(actions, text="Clear generated data", command=self._clear_generated)
        self.clear_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.validation_panel = CollapsiblePanel(
            constraints_body,
            "Validation",
            collapsed=False,
        )
        self.validation_panel.grid(row=2, column=0, sticky="nsew")
        self.validation_panel.body.columnconfigure(0, weight=1)
        self.validation_panel.body.rowconfigure(1, weight=1)
        self.validation_panel.body.rowconfigure(2, weight=0)

        validation_top = ttk.Frame(self.validation_panel.body)
        validation_top.grid(row=0, column=0, sticky="ew")
        validation_top.columnconfigure(1, weight=1)
        ttk.Button(validation_top, text="Run validation", command=self._run_validation).grid(row=0, column=0, sticky="w")
        ttk.Label(validation_top, textvariable=self.validation_summary_var).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.heatmap = ValidationHeatmap(self.validation_panel.body)
        self.heatmap.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.inline_validation = InlineValidationSummary(self.validation_panel.body, on_jump=self._jump_to_validation_issue)
        self.inline_validation.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self.fk_search = SearchEntry(self.validation_panel.body, on_change=self._on_fk_search_change, delay_ms=150)
        self.fk_search.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def _build_relationships_tab(self) -> None:
        self.relationships_tab.columnconfigure(0, weight=1)
        self.relationships_tab.rowconfigure(1, weight=1)

        rel_form_box = ttk.LabelFrame(self.relationships_tab, text="Relationship editor", padding=8)
        rel_form_box.grid(row=0, column=0, sticky="ew")
        rel_form_host = ttk.Frame(rel_form_box)
        rel_form_host.pack(fill="x")
        rel_form = FormBuilder(rel_form_host)
        self.fk_parent_combo = rel_form.add_combo("Parent table", self.fk_parent_table_var, [], readonly=True)
        self.fk_parent_combo.bind("<<ComboboxSelected>>", self._on_fk_selection_changed)
        self.fk_child_combo = rel_form.add_combo("Child table", self.fk_child_table_var, [], readonly=True)
        self.fk_child_combo.bind("<<ComboboxSelected>>", self._on_fk_selection_changed)
        self.fk_child_col_combo = rel_form.add_combo("Child FK column (int)", self.fk_child_column_var, [], readonly=True)
        self.fk_min_entry = rel_form.add_entry("Min children", self.fk_min_children_var, width=8)
        self.fk_max_entry = rel_form.add_entry("Max children", self.fk_max_children_var, width=8)
        self.add_fk_btn = ttk.Button(rel_form_box, text="Add relationship", command=self._add_fk)
        self.add_fk_btn.pack(fill="x", pady=(8, 0))

        fk_list = ttk.LabelFrame(self.relationships_tab, text="Defined relationships", padding=8)
        fk_list.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        fk_list.columnconfigure(0, weight=1)
        fk_list.rowconfigure(1, weight=1)

        self.relationships_search = SearchEntry(fk_list, on_change=self._on_fk_search_change, delay_ms=150)
        self.relationships_search.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.fks_table = TableView(fk_list, height=8)
        self.fks_table.grid(row=1, column=0, sticky="nsew")
        self.fks_table.set_columns(["parent", "parent_pk", "child", "child_fk", "min", "max"])
        self.fks_tree = self.fks_table.tree
        self.fks_tree.column("parent", width=120)
        self.fks_tree.column("parent_pk", width=100)
        self.fks_tree.column("child", width=120)
        self.fks_tree.column("child_fk", width=120)
        self.fks_tree.column("min", width=60, anchor="e")
        self.fks_tree.column("max", width=60, anchor="e")
        self.remove_fk_btn = ttk.Button(fk_list, text="Remove selected relationship", command=self._remove_selected_fk)
        self.remove_fk_btn.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _build_data_preview(self, parent: tk.Widget) -> None:
        preview_box = tk.LabelFrame(
            parent,
            text="Data Preview",
            bg=V2_DEMO_PANEL,
            fg="#1f1f1f",
            padx=8,
            pady=8,
            font=("Cambria", 12, "bold"),
        )
        preview_box.grid(row=1, column=0, sticky="nsew")
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(1, weight=1)

        preview_actions = tk.Frame(preview_box, bg=V2_DEMO_PANEL)
        preview_actions.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        preview_actions.columnconfigure(0, weight=1)
        self.preview_btn = ttk.Button(preview_actions, text="Refresh", command=self._refresh_preview)
        self.preview_btn.grid(row=0, column=1, sticky="e")

        preview_grid = tk.Frame(preview_box, bg=V2_DEMO_PANEL)
        preview_grid.grid(row=1, column=0, sticky="nsew")
        preview_grid.columnconfigure(0, weight=1)
        preview_grid.rowconfigure(0, weight=1)
        self.preview_table = TableView(preview_grid, height=9)
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

        self.progress = ttk.Progressbar(preview_box, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.register_busy_indicator(self.progress)

    def _build_bottom_actions(self) -> None:
        actions = tk.Frame(self._root_content, bg=V2_DEMO_BG)
        actions.pack(fill="x", pady=(10, 0))
        actions.columnconfigure(0, weight=1)

        right_buttons = tk.Frame(actions, bg=V2_DEMO_BG)
        right_buttons.grid(row=0, column=1, sticky="e")
        self.generate_btn = tk.Button(
            right_buttons,
            text="Generate Data",
            command=self._on_generate_project,
            bg=V2_DEMO_ACTION,
            fg="#ffffff",
            relief="flat",
            padx=16,
            pady=6,
        )
        self.generate_btn.pack(side="left", padx=(0, 8))
        self.save_btn = tk.Button(
            right_buttons,
            text="Save Schema",
            command=self._save_project,
            bg="#ece8de",
            fg="#1f1f1f",
            relief="flat",
            padx=14,
            pady=6,
        )
        self.save_btn.pack(side="left", padx=(0, 8))
        self.close_btn = tk.Button(
            right_buttons,
            text="Close",
            command=self._on_back_requested,
            bg="#ece8de",
            fg="#1f1f1f",
            relief="flat",
            padx=14,
            pady=6,
        )
        self.close_btn.pack(side="left")

    def _build_status_bar(self) -> None:
        self.status_strip = tk.Label(
            self._root_content,
            textvariable=self.status_var,
            anchor="w",
            bg="#d7ccba",
            fg="#242424",
            padx=10,
            pady=6,
            font=("Calibri", 10, "bold"),
        )
        self.status_strip.pack(fill="x", pady=(8, 0))

    def _on_back_requested(self) -> None:
        if self.confirm_discard_or_save(action_name="returning to Home v2"):
            self.app.show_screen("home_v2")

    def _set_running(self, running: bool, msg: str) -> None:
        self.is_running = running
        self.status_var.set(msg)
        if hasattr(self, "progress"):
            if running:
                self.progress.start(10)
            else:
                self.progress.stop()

        button_state = tk.DISABLED if running else tk.NORMAL
        readonly_or_disabled = "disabled" if running else "readonly"
        for name in (
            "generate_btn",
            "sample_btn",
            "export_btn",
            "clear_btn",
            "preview_btn",
            "save_btn",
            "close_btn",
            "mock_rules_btn",
            "distribution_btn",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(state=button_state)

        for name in ("export_option_combo", "preview_page_size_combo", "preview_table_combo"):
            widget = getattr(self, name, None)
            if widget is None:
                continue
            if name == "preview_page_size_combo":
                paging_enabled = bool(self.preview_paging_enabled_var.get())
                widget.configure(state=(readonly_or_disabled if (not running and paging_enabled) else tk.DISABLED))
            else:
                widget.configure(state=readonly_or_disabled)

        if hasattr(self, "preview_paging_chk"):
            self.preview_paging_chk.configure(state=button_state)
        self._set_table_editor_enabled((not running) and (self.selected_table_index is not None))

    def _open_params_json_editor(self) -> None:
        JsonEditorDialog(
            self,
            title="Generator Params JSON Editor",
            initial_text=self.col_params_var.get(),
            require_object=True,
            on_apply=self._on_params_json_apply,
        )

    def _jump_to_validation_issue(self, entry: InlineValidationEntry) -> None:
        payload = entry.jump_payload
        if not isinstance(payload, ValidationIssue):
            return

        if payload.scope == "fk":
            self._select_tab("relationships")
            self._jump_to_fk_issue(payload.table, payload.column)
            return
        self._select_tab("columns")
        self._jump_to_table_or_column_issue(payload.table, payload.column)

    def _jump_to_table_or_column_issue(self, table_name: str | None, column_name: str | None) -> None:
        if table_name is None:
            return
        for index, table in enumerate(self.project.tables):
            if table.table_name != table_name:
                continue

            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(index)
            self.tables_list.activate(index)
            self.tables_list.see(index)
            self._on_table_selected()
            if column_name:
                for item in self.columns_tree.get_children():
                    values = self.columns_tree.item(item, "values")
                    if values and str(values[0]) == column_name:
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

    def _jump_to_fk_issue(self, child_table: str | None, child_column: str | None) -> None:
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
            self.set_status(f"Jumped to validation location: FK '{table_value}.{column_value}'.")
            return

    def _on_table_selected(self, _event=None) -> None:
        super()._on_table_selected(_event)
        if self.selected_table_index is None:
            self._selected_table_title_var.set("No table selected")
            return
        table_name = self.project.tables[self.selected_table_index].table_name
        self._selected_table_title_var.set(f"{table_name.title()} Table")
        if table_name:
            self.preview_table_var.set(table_name)
            self._refresh_preview()

    def _refresh_columns_tree(self) -> None:
        for item in self.columns_tree.get_children():
            self.columns_tree.delete(item)

        if self.selected_table_index is None:
            return

        table = self.project.tables[self.selected_table_index]
        for idx, col in enumerate(table.columns):
            default_text = ""
            if isinstance(col.params, dict):
                default_value = col.params.get("default")
                if not isinstance(default_value, (dict, list)):
                    default_text = "" if default_value is None else str(default_value)
            self.columns_tree.insert(
                "",
                tk.END,
                values=(col.name, col.dtype, str(bool(col.nullable)), default_text),
                tags=(str(idx),),
            )

    def _on_columns_search_change(self, query: str) -> None:
        self._apply_tree_filter(self.columns_tree, query, key_columns=(0, 1, 2, 3))

    def _open_mock_data_rules(self) -> None:
        self._select_tab("constraints")
        self.constraints_rules_panel.expand()
        if hasattr(self, "table_business_key_entry"):
            self.table_business_key_entry.focus_set()
        self.set_status("Opened Mock Data Rules in Constraints.")

    def _open_distribution_config(self) -> None:
        self._select_tab("constraints")
        self.constraints_distribution_panel.expand()
        if hasattr(self, "export_option_combo"):
            self.export_option_combo.focus_set()
        self.set_status("Opened Distribution Config in Constraints.")

    def _select_tab(self, key: str) -> None:
        frame = self._tab_by_key.get(key)
        if frame is not None:
            self.details_tabs.select(frame)

    def _seed_demo_project(self) -> None:
        project = self._demo_project()
        rows = generate_project_rows(project)

        self.project = project
        self.generated_rows = rows
        self._preview_source_table = ""
        self._preview_source_rows = []
        self._preview_column_preferences.clear()

        self._suspend_project_meta_dirty = True
        try:
            self.project_name_var.set(project.name)
            self.seed_var.set(str(project.seed))
        finally:
            self._suspend_project_meta_dirty = False

        self._refresh_tables_list()
        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

        table_names = [table.table_name for table in project.tables]
        self.preview_table_combo["values"] = table_names
        target_table = "orders" if "orders" in table_names else (table_names[0] if table_names else "")
        if target_table:
            index = table_names.index(target_table)
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(index)
            self.tables_list.activate(index)
            self.tables_list.see(index)
            self._on_table_selected()
            self.preview_table_var.set(target_table)
            self._refresh_preview()

        self._run_validation()
        self.mark_clean()
        self.set_status("Schema Demo v2 ready with preloaded demo project.")

    def _demo_project(self) -> SchemaProject:
        return SchemaProject(
            name="schema_demo_v2_project",
            seed=20260217,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=80,
                    columns=[
                        ColumnSpec(name="customer_id", dtype="int", nullable=False, primary_key=True),
                        ColumnSpec(name="customer_name", dtype="text", nullable=False),
                        ColumnSpec(name="segment", dtype="text", nullable=False, choices=["Retail", "SMB", "Enterprise"]),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    row_count=160,
                    columns=[
                        ColumnSpec(name="order_id", dtype="int", nullable=False, primary_key=True),
                        ColumnSpec(name="customer_id", dtype="int", nullable=False),
                        ColumnSpec(
                            name="order_date",
                            dtype="date",
                            nullable=False,
                            generator="date",
                            params={"start": "2022-01-01", "end": "2025-12-31"},
                        ),
                        ColumnSpec(
                            name="total_amount",
                            dtype="decimal",
                            nullable=False,
                            generator="money",
                            params={"min": 25.0, "max": 1200.0, "decimals": 2},
                        ),
                        ColumnSpec(
                            name="status",
                            dtype="text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["NEW", "PAID", "SHIPPED"], "weights": [0.2, 0.5, 0.3]},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="products",
                    row_count=40,
                    columns=[
                        ColumnSpec(name="product_id", dtype="int", nullable=False, primary_key=True),
                        ColumnSpec(name="product_name", dtype="text", nullable=False),
                        ColumnSpec(
                            name="list_price",
                            dtype="decimal",
                            nullable=False,
                            generator="money",
                            params={"min": 5.0, "max": 350.0, "decimals": 2},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="shipments",
                    row_count=120,
                    columns=[
                        ColumnSpec(name="shipment_id", dtype="int", nullable=False, primary_key=True),
                        ColumnSpec(name="order_id", dtype="int", nullable=False),
                        ColumnSpec(
                            name="shipped_at",
                            dtype="datetime",
                            nullable=False,
                            generator="timestamp_utc",
                            params={"start": "2022-01-01T00:00:00Z", "end": "2025-12-31T23:59:59Z"},
                        ),
                        ColumnSpec(name="carrier", dtype="text", nullable=False, choices=["UPS", "USPS", "FedEx"]),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="customer_id",
                    parent_table="customers",
                    parent_column="customer_id",
                    min_children=1,
                    max_children=3,
                ),
                ForeignKeySpec(
                    child_table="shipments",
                    child_column="order_id",
                    parent_table="orders",
                    parent_column="order_id",
                    min_children=1,
                    max_children=2,
                ),
            ],
        )

    def _on_params_json_apply(self, pretty_json: str) -> None:
        self.col_params_var.set(pretty_json)
        self.set_status("Applied JSON editor content to Generator params JSON.")
        if hasattr(self, "toast_center"):
            self.toast_center.show_toast("Generator params updated from JSON editor.", level="success")
