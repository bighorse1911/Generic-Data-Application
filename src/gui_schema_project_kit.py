import tkinter as tk
from tkinter import messagebox, ttk

from src.generator_project import generate_project_rows
from src.gui_kit.forms import FormBuilder
from src.gui_kit.layout import BaseScreen
from src.gui_kit.panels import CollapsiblePanel, Tabs
from src.gui_kit.scroll import ScrollFrame
from src.gui_kit.table import TableView
from src.schema_project_model import validate_project
from src.gui_schema_project import (
    DTYPES,
    EXPORT_OPTIONS,
    GENERATORS,
    SCD_MODES,
    SchemaProjectDesignerScreen,
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

    def build_header(self) -> ttk.Frame:
        return BaseScreen.build_header(
            self,
            self._root_content,
            title="Schema Project Designer (Kit Preview)",
            back_command=self.app.go_home,
        )

    def build_project_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.schema_tab, "Project", collapsed=False)
        panel.pack(fill="x", pady=(0, 10))

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
        return panel

    def build_tables_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.schema_tab, "Tables", collapsed=False)
        panel.pack(fill="both", expand=True, pady=(0, 10))

        panel.body.columnconfigure(0, weight=1)
        panel.body.columnconfigure(1, weight=2)
        panel.body.rowconfigure(0, weight=1)

        left_box = ttk.LabelFrame(panel.body, text="Tables", padding=8)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_box.columnconfigure(0, weight=1)
        left_box.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(left_box)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tables_list = tk.Listbox(list_frame, height=10, exportselection=False)
        self.tables_list.grid(row=0, column=0, sticky="nsew")
        table_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tables_list.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        self.tables_list.configure(yscrollcommand=table_scroll.set)
        self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

        table_buttons = ttk.Frame(left_box)
        table_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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
        self.table_business_key_entry = table_form.add_entry(
            "Business key columns (comma)",
            self.table_business_key_var,
        )
        self.table_business_key_static_entry = table_form.add_entry(
            "Business key static columns (comma)",
            self.table_business_key_static_columns_var,
        )
        self.table_business_key_changing_entry = table_form.add_entry(
            "Business key changing columns (comma)",
            self.table_business_key_changing_columns_var,
        )
        self.table_scd_mode_combo = table_form.add_combo(
            "SCD mode",
            self.table_scd_mode_var,
            SCD_MODES,
            readonly=True,
        )
        self.table_scd_tracked_entry = table_form.add_entry(
            "SCD tracked columns (comma)",
            self.table_scd_tracked_columns_var,
        )
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
        self.col_generator_combo = column_form.add_combo("Generator", self.col_generator_var, GENERATORS, readonly=True)
        self.col_params_entry = column_form.add_entry("Generator params JSON", self.col_params_var)
        self.col_depends_entry = column_form.add_entry("Depends on column", self.col_depends_var)

        checks = ttk.Frame(editor_box)
        checks.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.col_nullable_chk = ttk.Checkbutton(checks, text="Nullable", variable=self.col_nullable_var)
        self.col_nullable_chk.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.col_pk_chk = ttk.Checkbutton(checks, text="Primary key (int only)", variable=self.col_pk_var)
        self.col_pk_chk.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.col_unique_chk = ttk.Checkbutton(checks, text="Unique", variable=self.col_unique_var)
        self.col_unique_chk.grid(row=0, column=2, sticky="w")

        self.add_col_btn = ttk.Button(editor_box, text="Add column to selected table", command=self._add_column)
        self.add_col_btn.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        columns_box = ttk.LabelFrame(panel.body, text="Columns in selected table", padding=8)
        columns_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        columns_box.columnconfigure(0, weight=1)
        columns_box.rowconfigure(0, weight=1)

        self.columns_table = TableView(columns_box, height=8)
        self.columns_table.grid(row=0, column=0, sticky="nsew")
        self.columns_table.set_columns(["name", "dtype", "nullable", "pk", "unique", "min", "max", "choices", "pattern"])
        self.columns_tree = self.columns_table.tree
        self.columns_tree.column("name", width=140)
        self.columns_tree.column("choices", width=180)
        self.columns_tree.column("pattern", width=180)

        column_actions = ttk.Frame(columns_box)
        column_actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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
        list_box.rowconfigure(0, weight=1)

        self.fks_table = TableView(list_box, height=8)
        self.fks_table.grid(row=0, column=0, sticky="nsew")
        self.fks_table.set_columns(["parent", "parent_pk", "child", "child_fk", "min", "max"])
        self.fks_tree = self.fks_table.tree
        self.fks_tree.column("parent", width=110)
        self.fks_tree.column("child", width=110)
        self.fks_tree.column("parent_pk", width=90)
        self.fks_tree.column("child_fk", width=90)
        self.fks_tree.column("min", width=60, anchor="e")
        self.fks_tree.column("max", width=60, anchor="e")

        self.remove_fk_btn = ttk.Button(list_box, text="Remove selected relationship", command=self._remove_selected_fk)
        self.remove_fk_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        return panel

    def build_generate_panel(self) -> CollapsiblePanel:
        panel = CollapsiblePanel(self.generate_tab, "Generate / Preview / Export / SQLite", collapsed=False)
        panel.pack(fill="both", expand=True)

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

        self.preview_btn = ttk.Button(left_preview, text="Refresh preview", command=self._refresh_preview)
        self.preview_btn.grid(row=4, column=0, sticky="ew")

        self.progress = ttk.Progressbar(left_preview, mode="indeterminate")
        self.progress.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        self.register_busy_indicator(self.progress)

        right_preview = ttk.Frame(preview_box)
        right_preview.grid(row=0, column=1, sticky="nsew")
        right_preview.columnconfigure(0, weight=1)
        right_preview.rowconfigure(0, weight=1)

        self.preview_table = TableView(right_preview, height=12)
        self.preview_table.grid(row=0, column=0, sticky="nsew")
        self.preview_tree = self.preview_table.tree
        return panel

    def build_status_bar(self) -> ttk.Frame:
        return BaseScreen.build_status_bar(self, self._root_content, include_progress=False)

    def _on_fk_selection_changed(self, _event=None) -> None:
        self._sync_fk_defaults()

    def _on_preview_table_selected(self, _event=None) -> None:
        self._refresh_preview()

    def _move_column_up(self) -> None:
        self._move_selected_column(-1)

    def _move_column_down(self) -> None:
        self._move_selected_column(1)

    def _on_generate_project(self) -> None:
        if self.is_running:
            return
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        self._set_running(True, "Generating data for all tables...")
        self.safe_threaded_job(
            lambda: generate_project_rows(self.project),
            self._on_generated_ok,
            lambda exc: self._on_job_failed(str(exc)),
        )

    def _on_create_insert_sqlite(self) -> None:
        if self.is_running:
            return
        if not self.generated_rows:
            messagebox.showwarning("No data", "Generate data first.")
            return

        db_path = self.db_path_var.get().strip()
        if not db_path:
            messagebox.showerror(
                "Missing DB path",
                "Generate / Preview / Export / SQLite panel: SQLite DB path is required. "
                "Fix: choose a SQLite database file path.",
            )
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        self._set_running(True, "Creating tables and inserting rows into SQLite...")

        def _sqlite_job() -> dict[str, int]:
            create_tables(db_path, self.project)
            return insert_project_rows(db_path, self.project, self.generated_rows, chunk_size=5000)

        self.safe_threaded_job(
            _sqlite_job,
            lambda counts: self._on_sqlite_ok(db_path, counts),
            lambda exc: self._on_job_failed(str(exc)),
        )

    def _on_generate_sample(self) -> None:
        if self.is_running:
            return

        if self.last_validation_errors > 0:
            messagebox.showerror(
                "Cannot generate",
                "Generate sample action: schema has validation errors. "
                "Fix: run validation and resolve all error cells first.",
            )
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        sample_project = self._make_sample_project(10)
        self._set_running(True, "Generating sample data (10 rows per root table)...")
        self.safe_threaded_job(
            lambda: generate_project_rows(sample_project),
            self._on_generated_ok,
            lambda exc: self._on_job_failed(str(exc)),
        )
