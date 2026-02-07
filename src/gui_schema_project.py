import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.config import AppConfig
from src.schema_project_model import (
    SchemaProject,
    TableSpec,
    ColumnSpec,
    validate_project,
)
from src.schema_project_io import save_project_to_json, load_project_from_json

logger = logging.getLogger("gui_schema_project")

DTYPES = ["int", "float", "text", "bool", "date", "datetime"]


class SchemaProjectDesignerScreen(ttk.Frame):
    """
    Phase 1 MVP:
    - Manage tables in a project
    - Edit selected table (name + row_count)
    - Edit selected table columns (add/remove/move, set PK)
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

        self._build()
        self._refresh_tables_list()
        self._set_table_editor_enabled(False)

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

        # Main area: tables list | table editor
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, pady=(10, 0))
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=3)
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

        # Right: table editor
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

        # columns actions
        # (Treeview doesn't have state in ttk; we just disable actions when no table selected)

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

            # default table has a PK column
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

            # select the new table
            self.selected_table_index = len(self.project.tables) - 1
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(self.selected_table_index)
            self.tables_list.activate(self.selected_table_index)
            self._load_selected_table_into_editor()

            self.status_var.set(f"Added table '{name}'.")
        except Exception as exc:
            messagebox.showerror("Add table failed", str(exc))

    def _remove_table(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            idx = self.selected_table_index
            removed = self.project.tables[idx].table_name

            tables = list(self.project.tables)
            tables.pop(idx)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,  # relationships UI comes in Phase 2
            )
            # allow temporarily empty? MVP requires at least one table, so enforce:
            validate_project(new_project)

            self.project = new_project
            self.selected_table_index = None
            self._refresh_tables_list()
            self._refresh_columns_tree()
            self._set_table_editor_enabled(False)

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

            # rename table: also rename PK column default if it matches old default pattern (optional)
            tables = list(self.project.tables)
            tables[idx] = TableSpec(table_name=new_name, columns=old.columns, row_count=row_count)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_tables_list()
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(idx)

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

            # reselect moved row
            children = self.columns_tree.get_children()
            if 0 <= new_idx < len(children):
                self.columns_tree.selection_set(children[new_idx])

        except Exception as exc:
            messagebox.showerror("Move column failed", str(exc))

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

            self.status_var.set(f"Loaded project: {path}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
