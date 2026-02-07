import logging
import tkinter as tk
import threading
import csv
import os

from src.generator_project import generate_project_rows
from src.storage_sqlite_project import create_tables, insert_project_rows

from tkinter import ttk, messagebox, filedialog

from src.config import AppConfig
from src.schema_project_model import (
    SchemaProject,
    TableSpec,
    ColumnSpec,
    ForeignKeySpec,
    validate_project,
)
from src.schema_project_io import save_project_to_json, load_project_from_json

logger = logging.getLogger("gui_schema_project")

DTYPES = ["int", "float", "text", "bool", "date", "datetime"]


class SchemaProjectDesignerScreen(ttk.Frame):
    """
    Schema Project Designer (Phase 1 + Phase 2):
    - Manage tables in a project
    - Edit selected table (name + row_count)
    - Edit selected table columns (add/remove/move, set PK)
    - Define FK relationships (parent->child) with cardinality min/max children
    - Save/load full project JSON
    """
    def __init__(self, parent: tk.Widget, app: "object", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg

        # In-memory project
        self.project = SchemaProject(name="my_project", seed=cfg.seed, tables=[], foreign_keys=[])

        # Selection state
        self.selected_table_index: int | None = None

        # Project-level vars
        self.project_name_var = tk.StringVar(value=self.project.name)
        self.seed_var = tk.StringVar(value=str(self.project.seed))
        self.status_var = tk.StringVar(value="Ready.")

        # Table editor vars
        self.table_name_var = tk.StringVar(value="")
        self.row_count_var = tk.StringVar(value="100")

        # Column form vars
        self.col_name_var = tk.StringVar(value="")
        self.col_dtype_var = tk.StringVar(value="text")
        self.col_nullable_var = tk.BooleanVar(value=True)
        self.col_pk_var = tk.BooleanVar(value=False)
        self.col_unique_var = tk.BooleanVar(value=False)
        self.col_min_var = tk.StringVar(value="")
        self.col_max_var = tk.StringVar(value="")
        self.col_choices_var = tk.StringVar(value="")
        self.col_pattern_var = tk.StringVar(value="")

        # Relationship editor vars
        self.fk_parent_table_var = tk.StringVar(value="")
        self.fk_child_table_var = tk.StringVar(value="")
        self.fk_child_column_var = tk.StringVar(value="")
        self.fk_min_children_var = tk.StringVar(value="1")
        self.fk_max_children_var = tk.StringVar(value="3")

        # Generation/preview state
        self.is_running = False
        self.generated_rows: dict[str, list[dict[str, object]]] = {}

        # Output / DB vars
        self.db_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "schema_project.db"))
        self.preview_table_var = tk.StringVar(value="")



        self._build()
        self._refresh_tables_list()
        self._set_table_editor_enabled(False)
        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

    # ---------------- UI layout ----------------
    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Button(header, text="← Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Schema Project Designer", font=("Segoe UI", 16, "bold")).pack(side="left", padx=12)

        # Project bar
        proj = ttk.LabelFrame(self, text="Project", padding=12)
        proj.pack(fill="x")

        proj.columnconfigure(1, weight=1)

        ttk.Label(proj, text="Project name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(proj, textvariable=self.project_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(proj, text="Seed:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(proj, textvariable=self.seed_var, width=12).grid(row=0, column=3, sticky="w", padx=6, pady=6)

        btns = ttk.Frame(proj)
        btns.grid(row=1, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Save project JSON", command=self._save_project).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Load project JSON", command=self._load_project).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Main area: tables list | table editor | relationships
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, pady=(10, 0))
        main.columnconfigure(0, weight=1)  # tables
        main.columnconfigure(1, weight=3)  # table editor
        main.columnconfigure(2, weight=2)  # relationships
        main.rowconfigure(0, weight=1)

        # Left: tables list
        left = ttk.LabelFrame(main, text="Tables", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.tables_list = tk.Listbox(left, height=12)
        self.tables_list.pack(fill="both", expand=True)
        self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

        left_btns = ttk.Frame(left)
        left_btns.pack(fill="x", pady=(10, 0))
        ttk.Button(left_btns, text="+ Add table", command=self._add_table).pack(fill="x", pady=4)
        ttk.Button(left_btns, text="Remove selected", command=self._remove_table).pack(fill="x", pady=4)

        # Middle: table editor
        right = ttk.LabelFrame(main, text="Table editor", padding=10)
        right.grid(row=0, column=1, sticky="nsew")

        # Table properties
        props = ttk.LabelFrame(right, text="Table properties", padding=10)
        props.pack(fill="x")
        props.columnconfigure(1, weight=1)

        ttk.Label(props, text="Table name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.table_name_entry = ttk.Entry(props, textvariable=self.table_name_var)
        self.table_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(props, text="Row count (root tables):").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.row_count_entry = ttk.Entry(props, textvariable=self.row_count_var)
        self.row_count_entry.grid(row=1, column=1, sticky="w", padx=6, pady=6)

        self.apply_table_btn = ttk.Button(props, text="Apply table changes", command=self._apply_table_changes)
        self.apply_table_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(10, 0))

        # Column editor
        col = ttk.LabelFrame(right, text="Add column", padding=10)
        col.pack(fill="x", pady=(10, 0))
        col.columnconfigure(1, weight=1)

        ttk.Label(col, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.col_name_entry = ttk.Entry(col, textvariable=self.col_name_var)
        self.col_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Type:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        self.col_dtype_combo = ttk.Combobox(col, values=DTYPES, textvariable=self.col_dtype_var, state="readonly", width=12)
        self.col_dtype_combo.grid(row=0, column=3, padx=6, pady=6)

        self.col_nullable_chk = ttk.Checkbutton(col, text="Nullable", variable=self.col_nullable_var)
        self.col_nullable_chk.grid(row=1, column=0, sticky="w", padx=6, pady=6)

        self.col_pk_chk = ttk.Checkbutton(col, text="Primary key (int only)", variable=self.col_pk_var)
        self.col_pk_chk.grid(row=1, column=1, sticky="w", padx=6, pady=6)

        self.col_unique_chk = ttk.Checkbutton(col, text="Unique", variable=self.col_unique_var)
        self.col_unique_chk.grid(row=1, column=2, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Min:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.col_min_entry = ttk.Entry(col, textvariable=self.col_min_var, width=12)
        self.col_min_entry.grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Max:").grid(row=2, column=2, sticky="w", padx=6, pady=6)
        self.col_max_entry = ttk.Entry(col, textvariable=self.col_max_var, width=12)
        self.col_max_entry.grid(row=2, column=3, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Choices (comma):").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        self.col_choices_entry = ttk.Entry(col, textvariable=self.col_choices_var)
        self.col_choices_entry.grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Regex pattern:").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        self.col_pattern_entry = ttk.Entry(col, textvariable=self.col_pattern_var)
        self.col_pattern_entry.grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        self.add_col_btn = ttk.Button(col, text="Add column to selected table", command=self._add_column)
        self.add_col_btn.grid(row=5, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))

        # Columns table
        cols_frame = ttk.LabelFrame(right, text="Columns", padding=8)
        cols_frame.pack(fill="both", expand=True, pady=(10, 0))

        cols = ("name", "dtype", "nullable", "pk", "unique", "min", "max", "choices", "pattern")
        self.columns_tree = ttk.Treeview(cols_frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.columns_tree.heading(c, text=c)
            self.columns_tree.column(c, width=110, anchor="w", stretch=True)
        self.columns_tree.column("name", width=140)
        self.columns_tree.column("choices", width=180)
        self.columns_tree.column("pattern", width=180)

        yscroll = ttk.Scrollbar(cols_frame, orient="vertical", command=self.columns_tree.yview)
        self.columns_tree.configure(yscrollcommand=yscroll.set)

        self.columns_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        col_actions = ttk.Frame(right)
        col_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(col_actions, text="Remove selected column", command=self._remove_selected_column).pack(side="left", padx=(0, 6))
        ttk.Button(col_actions, text="Move up", command=lambda: self._move_selected_column(-1)).pack(side="left", padx=6)
        ttk.Button(col_actions, text="Move down", command=lambda: self._move_selected_column(1)).pack(side="left", padx=6)

        # Right: relationships editor
        rel = ttk.LabelFrame(main, text="Relationships (FKs)", padding=10)
        rel.grid(row=0, column=2, sticky="nsew")
        rel.columnconfigure(1, weight=1)
        rel.rowconfigure(6, weight=1)

        ttk.Label(rel, text="Parent table:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.fk_parent_combo = ttk.Combobox(rel, textvariable=self.fk_parent_table_var, state="readonly")
        self.fk_parent_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        self.fk_parent_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_fk_defaults())

        ttk.Label(rel, text="Child table:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.fk_child_combo = ttk.Combobox(rel, textvariable=self.fk_child_table_var, state="readonly")
        self.fk_child_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        self.fk_child_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_fk_defaults())

        ttk.Label(rel, text="Child FK column (int):").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.fk_child_col_combo = ttk.Combobox(rel, textvariable=self.fk_child_column_var, state="readonly")
        self.fk_child_col_combo.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(rel, text="Min children:").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(rel, textvariable=self.fk_min_children_var, width=8).grid(row=3, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(rel, text="Max children:").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(rel, textvariable=self.fk_max_children_var, width=8).grid(row=4, column=1, sticky="w", padx=6, pady=6)

        self.add_fk_btn = ttk.Button(rel, text="Add relationship", command=self._add_fk)
        self.add_fk_btn.grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=(10, 8))

        fk_frame = ttk.LabelFrame(rel, text="Defined relationships", padding=8)
        fk_frame.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=6, pady=(6, 0))
        fk_frame.rowconfigure(0, weight=1)
        fk_frame.columnconfigure(0, weight=1)

        fk_cols = ("parent", "parent_pk", "child", "child_fk", "min", "max")
        self.fks_tree = ttk.Treeview(fk_frame, columns=fk_cols, show="headings", height=10)
        for c in fk_cols:
            self.fks_tree.heading(c, text=c)
            self.fks_tree.column(c, width=110, anchor="w", stretch=True)
        self.fks_tree.column("parent", width=110)
        self.fks_tree.column("child", width=110)
        self.fks_tree.column("parent_pk", width=90)
        self.fks_tree.column("child_fk", width=90)
        self.fks_tree.column("min", width=60, anchor="e")
        self.fks_tree.column("max", width=60, anchor="e")

        y2 = ttk.Scrollbar(fk_frame, orient="vertical", command=self.fks_tree.yview)
        self.fks_tree.configure(yscrollcommand=y2.set)

        self.fks_tree.grid(row=0, column=0, sticky="nsew")
        y2.grid(row=0, column=1, sticky="ns")

        self.remove_fk_btn = ttk.Button(rel, text="Remove selected relationship", command=self._remove_selected_fk)
        self.remove_fk_btn.grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 0))


        # -------- Phase 3: Generate / Preview / Export / SQLite --------
        bottom = ttk.LabelFrame(self, text="Generate / Preview / Export / SQLite", padding=12)
        bottom.pack(fill="both", expand=True, pady=(12, 0))
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(2, weight=1)

        # Row 0: DB path
        ttk.Label(bottom, text="SQLite DB path:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(bottom, textvariable=self.db_path_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(bottom, text="Browse…", command=self._browse_db_path).grid(row=0, column=2, padx=6, pady=6)

        # Row 1: Action buttons
        actions = ttk.Frame(bottom)
        actions.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 10))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        actions.columnconfigure(3, weight=1)

        self.generate_btn = ttk.Button(actions, text="Generate data (all tables)", command=self._on_generate_project)
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=4)

        self.export_btn = ttk.Button(actions, text="Export to CSV (folder)", command=self._on_export_csv)
        self.export_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.create_insert_btn = ttk.Button(actions, text="Create tables + Insert into SQLite", command=self._on_create_insert_sqlite)
        self.create_insert_btn.grid(row=0, column=2, sticky="ew", padx=4)

        self.clear_btn = ttk.Button(actions, text="Clear generated data", command=self._clear_generated)
        self.clear_btn.grid(row=0, column=3, sticky="ew", padx=4)

        # Row 2: Preview area (left controls + right Treeview)
        preview_area = ttk.Frame(bottom)
        preview_area.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
        preview_area.columnconfigure(1, weight=1)
        preview_area.rowconfigure(0, weight=1)

        left_preview = ttk.LabelFrame(preview_area, text="Preview", padding=10)
        left_preview.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left_preview.columnconfigure(0, weight=1)

        ttk.Label(left_preview, text="Table:").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.preview_table_combo = ttk.Combobox(left_preview, textvariable=self.preview_table_var, state="readonly")
        self.preview_table_combo.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.preview_table_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())

        ttk.Label(left_preview, text="Max rows to show:").grid(row=2, column=0, sticky="w")
        self.preview_limit_var = tk.StringVar(value="200")
        ttk.Entry(left_preview, textvariable=self.preview_limit_var, width=10).grid(row=3, column=0, sticky="w", pady=(0, 10))

        self.preview_btn = ttk.Button(left_preview, text="Refresh preview", command=self._refresh_preview)
        self.preview_btn.grid(row=4, column=0, sticky="ew")

        self.progress = ttk.Progressbar(left_preview, mode="indeterminate")
        self.progress.grid(row=5, column=0, sticky="ew", pady=(14, 0))

        right_preview = ttk.LabelFrame(preview_area, text="Data preview", padding=8)
        right_preview.grid(row=0, column=1, sticky="nsew")
        right_preview.rowconfigure(0, weight=1)
        right_preview.columnconfigure(0, weight=1)

        self.preview_tree = ttk.Treeview(right_preview, show="headings")
        y3 = ttk.Scrollbar(right_preview, orient="vertical", command=self.preview_tree.yview)
        x3 = ttk.Scrollbar(right_preview, orient="horizontal", command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=y3.set, xscrollcommand=x3.set)

        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        y3.grid(row=0, column=1, sticky="ns")
        x3.grid(row=1, column=0, sticky="ew")



        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(10, 0))

    # ---------------- Helpers ----------------
    def _set_table_editor_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED

        self.table_name_entry.configure(state=state)
        self.row_count_entry.configure(state=state)
        self.apply_table_btn.configure(state=state)

        self.col_name_entry.configure(state=state)
        self.col_dtype_combo.configure(state=("readonly" if enabled else tk.DISABLED))
        self.col_nullable_chk.configure(state=state)
        self.col_pk_chk.configure(state=state)
        self.col_unique_chk.configure(state=state)
        self.col_min_entry.configure(state=state)
        self.col_max_entry.configure(state=state)
        self.col_choices_entry.configure(state=state)
        self.col_pattern_entry.configure(state=state)
        self.add_col_btn.configure(state=state)

    def _refresh_tables_list(self) -> None:
        self.tables_list.delete(0, tk.END)
        for t in self.project.tables:
            self.tables_list.insert(tk.END, t.table_name)

    def _refresh_columns_tree(self) -> None:
        for item in self.columns_tree.get_children():
            self.columns_tree.delete(item)

        if self.selected_table_index is None:
            return

        t = self.project.tables[self.selected_table_index]
        for i, c in enumerate(t.columns):
            self.columns_tree.insert(
                "",
                tk.END,
                values=(
                    c.name, c.dtype, c.nullable, c.primary_key, c.unique,
                    c.min_value, c.max_value,
                    ", ".join(c.choices) if c.choices else "",
                    c.pattern or "",
                ),
                tags=(str(i),),
            )

    def _selected_column_index(self) -> int | None:
        sel = self.columns_tree.selection()
        if not sel:
            return None
        return int(self.columns_tree.item(sel[0], "tags")[0])

    def _apply_project_vars_to_model(self) -> None:
        name = self.project_name_var.get().strip()
        seed = int(self.seed_var.get().strip())
        self.project = SchemaProject(
            name=name,
            seed=seed,
            tables=self.project.tables,
            foreign_keys=self.project.foreign_keys,
        )

    # ----- FK helpers -----
    def _table_pk_name(self, table_name: str) -> str:
        for t in self.project.tables:
            if t.table_name == table_name:
                for c in t.columns:
                    if c.primary_key:
                        return c.name
        raise ValueError(f"Table '{table_name}' has no primary key (should not happen).")

    def _int_columns(self, table_name: str) -> list[str]:
        for t in self.project.tables:
            if t.table_name == table_name:
                return [c.name for c in t.columns if c.dtype == "int"]
        return []

    def _refresh_fk_dropdowns(self) -> None:
        names = [t.table_name for t in self.project.tables]

        self.fk_parent_combo["values"] = names
        self.fk_child_combo["values"] = names

        if names:
            if not self.fk_parent_table_var.get():
                self.fk_parent_table_var.set(names[0])
            if not self.fk_child_table_var.get():
                self.fk_child_table_var.set(names[0])

        self._sync_fk_defaults()

    def _sync_fk_defaults(self) -> None:
        child = self.fk_child_table_var.get().strip()
        if not child:
            self.fk_child_col_combo["values"] = []
            self.fk_child_column_var.set("")
            return

        int_cols = self._int_columns(child)
        self.fk_child_col_combo["values"] = int_cols

        pk = ""
        try:
            pk = self._table_pk_name(child)
        except Exception:
            pk = ""

        preferred = ""
        for c in int_cols:
            if c != pk and c.endswith("_id"):
                preferred = c
                break

        if preferred:
            self.fk_child_column_var.set(preferred)
        elif int_cols:
            non_pk = [c for c in int_cols if c != pk]
            self.fk_child_column_var.set(non_pk[0] if non_pk else int_cols[0])
        else:
            self.fk_child_column_var.set("")

    def _refresh_fks_tree(self) -> None:
        for item in self.fks_tree.get_children():
            self.fks_tree.delete(item)

        for i, fk in enumerate(self.project.foreign_keys):
            self.fks_tree.insert(
                "",
                tk.END,
                values=(fk.parent_table, fk.parent_column, fk.child_table, fk.child_column, fk.min_children, fk.max_children),
                tags=(str(i),),
            )

    def _selected_fk_index(self) -> int | None:
        sel = self.fks_tree.selection()
        if not sel:
            return None
        return int(self.fks_tree.item(sel[0], "tags")[0])

    # ---------------- Table list actions ----------------
    def _add_table(self) -> None:
        try:
            self._apply_project_vars_to_model()
            base_name = "new_table"
            existing = {t.table_name for t in self.project.tables}
            n = 1
            name = base_name
            while name in existing:
                n += 1
                name = f"{base_name}_{n}"

            new_table = TableSpec(
                table_name=name,
                row_count=100,
                columns=[
                    ColumnSpec(name=f"{name}_id", dtype="int", nullable=False, primary_key=True),
                ],
            )

            tables = list(self.project.tables) + [new_table]
            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_tables_list()

            self.selected_table_index = len(self.project.tables) - 1
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(self.selected_table_index)
            self.tables_list.activate(self.selected_table_index)
            self._load_selected_table_into_editor()

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set(f"Added table '{name}'.")
        except Exception as exc:
            messagebox.showerror("Add table failed", str(exc))

    def _remove_table(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            idx = self.selected_table_index
            removed = self.project.tables[idx].table_name

            # remove any FK where this table is parent or child
            fks = [fk for fk in self.project.foreign_keys if fk.parent_table != removed and fk.child_table != removed]

            tables = list(self.project.tables)
            tables.pop(idx)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self.selected_table_index = None
            self._refresh_tables_list()
            self._refresh_columns_tree()
            self._set_table_editor_enabled(False)

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set(f"Removed table '{removed}'.")
        except Exception as exc:
            messagebox.showerror("Remove table failed", str(exc))

    def _on_table_selected(self, _event=None) -> None:
        sel = self.tables_list.curselection()
        if not sel:
            self.selected_table_index = None
            self._set_table_editor_enabled(False)
            self._refresh_columns_tree()
            return
        self.selected_table_index = int(sel[0])
        self._load_selected_table_into_editor()

    def _load_selected_table_into_editor(self) -> None:
        if self.selected_table_index is None:
            return
        t = self.project.tables[self.selected_table_index]
        self.table_name_var.set(t.table_name)
        self.row_count_var.set(str(t.row_count))
        self._set_table_editor_enabled(True)
        self._refresh_columns_tree()

    def _apply_table_changes(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            self._apply_project_vars_to_model()

            idx = self.selected_table_index
            old = self.project.tables[idx]

            new_name = self.table_name_var.get().strip()
            if not new_name:
                raise ValueError("Table name cannot be empty.")

            row_count = int(self.row_count_var.get().strip())
            if row_count <= 0:
                raise ValueError("Row count must be > 0.")

            # rename references in existing foreign keys
            fks = []
            for fk in self.project.foreign_keys:
                fks.append(
                    ForeignKeySpec(
                        child_table=(new_name if fk.child_table == old.table_name else fk.child_table),
                        child_column=fk.child_column,
                        parent_table=(new_name if fk.parent_table == old.table_name else fk.parent_table),
                        parent_column=fk.parent_column,
                        min_children=fk.min_children,
                        max_children=fk.max_children,
                    )
                )

            tables = list(self.project.tables)
            tables[idx] = TableSpec(table_name=new_name, columns=old.columns, row_count=row_count)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_tables_list()
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(idx)

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set("Applied table changes.")
        except Exception as exc:
            messagebox.showerror("Apply failed", str(exc))

    # ---------------- Column actions ----------------
    def _add_column(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            self._apply_project_vars_to_model()
            idx = self.selected_table_index
            t = self.project.tables[idx]

            name = self.col_name_var.get().strip()
            dtype = self.col_dtype_var.get().strip()

            if not name:
                raise ValueError("Column name cannot be empty.")

            nullable = bool(self.col_nullable_var.get())
            pk = bool(self.col_pk_var.get())
            unique = bool(self.col_unique_var.get())

            min_s = self.col_min_var.get().strip()
            max_s = self.col_max_var.get().strip()
            min_v = float(min_s) if min_s != "" else None
            max_v = float(max_s) if max_s != "" else None

            choices_s = self.col_choices_var.get().strip()
            choices = [c.strip() for c in choices_s.split(",") if c.strip()] if choices_s else None

            pattern = self.col_pattern_var.get().strip() or None

            new_col = ColumnSpec(
                name=name,
                dtype=dtype,  # type: ignore
                nullable=nullable,
                primary_key=pk,
                unique=unique,
                min_value=min_v,
                max_value=max_v,
                choices=choices,
                pattern=pattern,
            )

            cols = list(t.columns)

            if any(c.name == new_col.name for c in cols):
                raise ValueError(f"Column '{new_col.name}' already exists on table '{t.table_name}'.")

            # If setting PK, unset existing PK (MVP allows only one PK)
            if new_col.primary_key:
                if new_col.dtype != "int":
                    raise ValueError("Primary key must be dtype=int in this MVP.")
                cols = [ColumnSpec(**{**c.__dict__, "primary_key": False}) for c in cols]  # type: ignore

            cols.append(new_col)

            tables = list(self.project.tables)
            tables[idx] = TableSpec(table_name=t.table_name, columns=cols, row_count=t.row_count)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project

            # clear form
            self.col_name_var.set("")
            self.col_min_var.set("")
            self.col_max_var.set("")
            self.col_choices_var.set("")
            self.col_pattern_var.set("")
            self.col_pk_var.set(False)

            self._refresh_columns_tree()
            self._refresh_fk_dropdowns()

            self.status_var.set("Column added.")
        except Exception as exc:
            messagebox.showerror("Add column failed", str(exc))

    def _remove_selected_column(self) -> None:
        if self.selected_table_index is None:
            return
        col_idx = self._selected_column_index()
        if col_idx is None:
            return
        try:
            self._apply_project_vars_to_model()
            t_idx = self.selected_table_index
            t = self.project.tables[t_idx]

            cols = list(t.columns)
            removed = cols[col_idx].name

            # prevent removing a column that is used in an FK
            for fk in self.project.foreign_keys:
                if fk.child_table == t.table_name and fk.child_column == removed:
                    raise ValueError("Cannot remove: column is used as a child FK.")
                if fk.parent_table == t.table_name and fk.parent_column == removed:
                    raise ValueError("Cannot remove: column is used as a parent PK reference in an FK.")

            cols.pop(col_idx)

            tables = list(self.project.tables)
            tables[t_idx] = TableSpec(table_name=t.table_name, columns=cols, row_count=t.row_count)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_columns_tree()
            self._refresh_fk_dropdowns()
            self.status_var.set(f"Removed column '{removed}'.")
        except Exception as exc:
            messagebox.showerror("Remove column failed", str(exc))

    def _move_selected_column(self, delta: int) -> None:
        if self.selected_table_index is None:
            return
        col_idx = self._selected_column_index()
        if col_idx is None:
            return
        try:
            self._apply_project_vars_to_model()
            t_idx = self.selected_table_index
            t = self.project.tables[t_idx]

            new_idx = col_idx + delta
            if new_idx < 0 or new_idx >= len(t.columns):
                return

            cols = list(t.columns)
            cols[col_idx], cols[new_idx] = cols[new_idx], cols[col_idx]

            tables = list(self.project.tables)
            tables[t_idx] = TableSpec(table_name=t.table_name, columns=cols, row_count=t.row_count)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_columns_tree()
            self._refresh_fk_dropdowns()

            children = self.columns_tree.get_children()
            if 0 <= new_idx < len(children):
                self.columns_tree.selection_set(children[new_idx])

        except Exception as exc:
            messagebox.showerror("Move column failed", str(exc))

    # ---------------- Relationship actions ----------------
    def _add_fk(self) -> None:
        try:
            self._apply_project_vars_to_model()

            parent = self.fk_parent_table_var.get().strip()
            child = self.fk_child_table_var.get().strip()
            child_col = self.fk_child_column_var.get().strip()

            if not parent or not child or not child_col:
                raise ValueError("Choose parent table, child table, and child FK column.")

            if parent == child:
                raise ValueError("Parent table and child table must be different.")

            parent_pk = self._table_pk_name(parent)
            child_pk = self._table_pk_name(child)

            min_k = int(self.fk_min_children_var.get().strip())
            max_k = int(self.fk_max_children_var.get().strip())
            if min_k <= 0 or max_k <= 0:
                raise ValueError("Min/max children must be > 0.")
            if min_k > max_k:
                raise ValueError("Min children cannot exceed max children.")

            # MVP constraint: child can only have one FK
            if any(fk.child_table == child for fk in self.project.foreign_keys):
                raise ValueError(f"Table '{child}' already has a foreign key (MVP supports 1 FK per child table).")

            if child_col == child_pk:
                raise ValueError("Child FK column cannot be the child's primary key column.")

            if child_col not in self._int_columns(child):
                raise ValueError("Child FK column must be an int column.")

            fks = list(self.project.foreign_keys)
            fks.append(
                ForeignKeySpec(
                    child_table=child,
                    child_column=child_col,
                    parent_table=parent,
                    parent_column=parent_pk,
                    min_children=min_k,
                    max_children=max_k,
                )
            )

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=self.project.tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_fks_tree()
            self.status_var.set("Relationship added.")
        except Exception as exc:
            messagebox.showerror("Add relationship failed", str(exc))

    def _remove_selected_fk(self) -> None:
        idx = self._selected_fk_index()
        if idx is None:
            return
        try:
            self._apply_project_vars_to_model()

            fks = list(self.project.foreign_keys)
            removed = fks[idx]
            fks.pop(idx)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=self.project.tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_fks_tree()
            self.status_var.set(
                f"Removed relationship: {removed.parent_table}.{removed.parent_column} → {removed.child_table}.{removed.child_column}"
            )
        except Exception as exc:
            messagebox.showerror("Remove relationship failed", str(exc))

    def _browse_db_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose SQLite database file",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path_var.set(path)
    def _set_running(self, running: bool, msg: str) -> None:
        self.is_running = running
        self.status_var.set(msg)
        if running:
            self.progress.start(10)
        else:
            self.progress.stop()

        # disable buttons while running
        state = tk.DISABLED if running else tk.NORMAL
        self.generate_btn.configure(state=state)
        self.export_btn.configure(state=state)
        self.create_insert_btn.configure(state=state)
        self.clear_btn.configure(state=state)
        self.preview_btn.configure(state=state)

    def _on_generate_project(self) -> None:
        if self.is_running:
            return
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        self._set_running(True, "Generating data for all tables…")

        def work():
            try:
                rows = generate_project_rows(self.project)
                self.after(0, lambda: self._on_generated_ok(rows))
            except Exception as exc:
                logger.exception("Generation failed: %s", exc)
                self.after(0, lambda: self._on_job_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
        self.generated_rows = rows
        self._set_running(False, "Generation complete.")

        # update preview table dropdown
        table_names = list(rows.keys())
        self.preview_table_combo["values"] = table_names
        if table_names:
            if not self.preview_table_var.get() or self.preview_table_var.get() not in table_names:
                self.preview_table_var.set(table_names[0])
            self._refresh_preview()

        # quick summary
        summary = "\n".join([f"{t}: {len(r)} rows" for t, r in rows.items()])
        messagebox.showinfo("Generated", f"Generated data:\n{summary}")

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

        rows = self.generated_rows[table][:limit]
        self._render_preview_rows(rows)

    def _clear_preview_tree(self) -> None:
        self.preview_tree["columns"] = ()
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

    def _render_preview_rows(self, rows: list[dict[str, object]]) -> None:
        self._clear_preview_tree()
        if not rows:
            return

        # Determine columns from keys of first row
        cols = list(rows[0].keys())
        self.preview_tree["columns"] = tuple(cols)

        for c in cols:
            self.preview_tree.heading(c, text=c)
            self.preview_tree.column(c, width=140, anchor="w", stretch=True)

        for r in rows:
            values = [r.get(c) for c in cols]
            self.preview_tree.insert("", tk.END, values=values)

    def _on_export_csv(self) -> None:
        if self.is_running:
            return
        if not self.generated_rows:
            messagebox.showwarning("Nothing to export", "Generate data first.")
            return

        folder = filedialog.askdirectory(title="Choose a folder to export CSVs into")
        if not folder:
            return

        try:
            for table, rows in self.generated_rows.items():
                if not rows:
                    continue
                path = os.path.join(folder, f"{table}.csv")
                cols = list(rows[0].keys())

                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(cols)
                    for r in rows:
                        w.writerow([r.get(c) for c in cols])

            self.status_var.set(f"Exported CSVs to: {folder}")
            messagebox.showinfo("Export complete", f"Exported one CSV per table into:\n{folder}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _on_create_insert_sqlite(self) -> None:
        if self.is_running:
            return
        if not self.generated_rows:
            messagebox.showwarning("No data", "Generate data first.")
            return

        db_path = self.db_path_var.get().strip()
        if not db_path:
            messagebox.showerror("Missing DB path", "Please choose a SQLite DB path.")
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        self._set_running(True, "Creating tables and inserting rows into SQLite…")

        def work():
            try:
                create_tables(db_path, self.project)
                counts = insert_project_rows(db_path, self.project, self.generated_rows, chunk_size=5000)
                self.after(0, lambda: self._on_sqlite_ok(db_path, counts))
            except Exception as exc:
                logger.exception("SQLite insert failed: %s", exc)
                self.after(0, lambda: self._on_job_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
        self._set_running(False, "SQLite insert complete.")
        summary = "\n".join([f"{t}: {n} inserted" for t, n in counts.items()])
        messagebox.showinfo("SQLite complete", f"Inserted into:\n{db_path}\n\n{summary}")

    def _clear_generated(self) -> None:
        self.generated_rows = {}
        self.preview_table_combo["values"] = []
        self.preview_table_var.set("")
        self._clear_preview_tree()
        self.status_var.set("Cleared generated data.")

    def _on_job_failed(self, msg: str) -> None:
        self._set_running(False, "Failed.")
        messagebox.showerror("Error", msg)



    # ---------------- Save / Load ----------------
    def _save_project(self) -> None:
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)

            path = filedialog.asksaveasfilename(
                title="Save project as JSON",
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            save_project_to_json(self.project, path)
            self.status_var.set(f"Saved project: {path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def _load_project(self) -> None:
        try:
            path = filedialog.askopenfilename(
                title="Load project JSON",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            project = load_project_from_json(path)
            self.project = project
            self.project_name_var.set(project.name)
            self.seed_var.set(str(project.seed))

            self.selected_table_index = None
            self._refresh_tables_list()
            self._refresh_columns_tree()
            self._set_table_editor_enabled(False)

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set(f"Loaded project: {path}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
