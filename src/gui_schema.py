import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.config import AppConfig
from src.schema_model import TableSchema, ColumnSpec, validate_schema
from src.schema_io import save_schema_to_json, load_schema_from_json
from src.generator_schema import generate_rows
from src.storage_sqlite_schema import create_table_from_schema, insert_rows

logger = logging.getLogger("gui_schema")

DTYPES = ["int", "float", "text", "bool", "date", "datetime"]

class SchemaDesignerScreen(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "object", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg

        self.is_running = False
        self.preview_rows: list[dict[str, object]] = []

        # schema-level variables
        self.table_name_var = tk.StringVar(value="my_table")
        self.seed_var = tk.StringVar(value=str(cfg.seed))
        self.db_path_var = tk.StringVar(value=cfg.sqlite_db_path)
        self.preview_n_var = tk.StringVar(value="50")
        self.insert_n_var = tk.StringVar(value="1000")
        self.status_var = tk.StringVar(value="Ready.")

        # new-column form variables
        self.col_name_var = tk.StringVar(value="")
        self.col_dtype_var = tk.StringVar(value="text")
        self.col_nullable_var = tk.BooleanVar(value=True)
        self.col_pk_var = tk.BooleanVar(value=False)
        self.col_unique_var = tk.BooleanVar(value=False)
        self.col_min_var = tk.StringVar(value="")
        self.col_max_var = tk.StringVar(value="")
        self.col_choices_var = tk.StringVar(value="")  # comma-separated
        self.col_pattern_var = tk.StringVar(value="")

        self.schema = TableSchema(table_name="my_table", columns=[], seed=cfg.seed)

        self._build()
        self._refresh_columns_table()
        self._refresh_ui_state()

    # ---------- UI ----------
    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Button(header, text="← Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Schema Designer", font=("Segoe UI", 16, "bold")).pack(side="left", padx=12)

        top = ttk.LabelFrame(self, text="Schema", padding=12)
        top.pack(fill="x")

        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Table name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(top, textvariable=self.table_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(top, text="Seed:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(top, textvariable=self.seed_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(top, text="SQLite DB path:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(top, textvariable=self.db_path_var).grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(top, text="Browse…", command=self._browse_db).grid(row=2, column=2, padx=6, pady=6)

        # Schema save/load
        schema_btns = ttk.Frame(top)
        schema_btns.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(10, 0))
        schema_btns.columnconfigure(0, weight=1)
        schema_btns.columnconfigure(1, weight=1)

        ttk.Button(schema_btns, text="Save schema JSON", command=self._save_schema).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(schema_btns, text="Load schema JSON", command=self._load_schema).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Column editor
        col = ttk.LabelFrame(self, text="Add column", padding=12)
        col.pack(fill="x", pady=(10, 0))
        col.columnconfigure(1, weight=1)

        ttk.Label(col, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(col, textvariable=self.col_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Type:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Combobox(col, values=DTYPES, textvariable=self.col_dtype_var, state="readonly", width=12).grid(row=0, column=3, padx=6, pady=6)

        ttk.Checkbutton(col, text="Nullable", variable=self.col_nullable_var).grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Checkbutton(col, text="Primary key", variable=self.col_pk_var).grid(row=1, column=1, sticky="w", padx=6, pady=6)
        ttk.Checkbutton(col, text="Unique", variable=self.col_unique_var).grid(row=1, column=2, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Min:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(col, textvariable=self.col_min_var, width=12).grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Max:").grid(row=2, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(col, textvariable=self.col_max_var, width=12).grid(row=2, column=3, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Choices (comma):").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(col, textvariable=self.col_choices_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Regex pattern (optional):").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(col, textvariable=self.col_pattern_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Button(col, text="Add column", command=self._add_column).grid(row=5, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))

        # Columns table + actions
        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, pady=(10, 0))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=1)
        mid.rowconfigure(0, weight=1)

        table_frame = ttk.LabelFrame(mid, text="Columns", padding=8)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        actions = ttk.LabelFrame(mid, text="Actions", padding=8)
        actions.grid(row=0, column=1, sticky="nsew")

        # Columns Treeview
        cols = ("name", "dtype", "nullable", "pk", "unique", "min", "max", "choices", "pattern")
        self.columns_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        for c in cols:
            self.columns_tree.heading(c, text=c)
            self.columns_tree.column(c, width=110, anchor="w", stretch=True)
        self.columns_tree.column("name", width=140)
        self.columns_tree.column("choices", width=180)
        self.columns_tree.column("pattern", width=180)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.columns_tree.yview)
        self.columns_tree.configure(yscrollcommand=yscroll.set)

        self.columns_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        # Action buttons
        ttk.Button(actions, text="Remove selected column", command=self._remove_selected).pack(fill="x", pady=6)
        ttk.Button(actions, text="Move selected up", command=lambda: self._move_selected(-1)).pack(fill="x", pady=6)
        ttk.Button(actions, text="Move selected down", command=lambda: self._move_selected(1)).pack(fill="x", pady=6)

        ttk.Separator(actions).pack(fill="x", pady=10)

        ttk.Label(actions, text="Preview rows:").pack(anchor="w")
        ttk.Entry(actions, textvariable=self.preview_n_var).pack(fill="x", pady=6)
        ttk.Button(actions, text="Generate Preview", command=self._on_preview).pack(fill="x", pady=6)
        ttk.Button(actions, text="Export Preview to CSV", command=self._export_preview).pack(fill="x", pady=6)

        ttk.Separator(actions).pack(fill="x", pady=10)

        ttk.Label(actions, text="Insert rows into DB:").pack(anchor="w")
        ttk.Entry(actions, textvariable=self.insert_n_var).pack(fill="x", pady=6)
        ttk.Button(actions, text="Create table + Insert", command=self._on_insert).pack(fill="x", pady=6)

        self.progress = ttk.Progressbar(actions, mode="indeterminate")
        self.progress.pack(fill="x", pady=(14, 6))

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(10, 0))

    # ---------- Schema build ----------
    def _current_schema(self) -> TableSchema:
        table = self.table_name_var.get().strip()
        seed = int(self.seed_var.get().strip())
        return TableSchema(table_name=table, columns=self.schema.columns, seed=seed)

    def _add_column(self) -> None:
        try:
            name = self.col_name_var.get().strip()
            dtype = self.col_dtype_var.get().strip()

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

            col = ColumnSpec(
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

            # enforce “one PK” rule by unsetting others if needed
            cols = list(self.schema.columns)
            if col.primary_key:
                cols = [ColumnSpec(**{**c.__dict__, "primary_key": False}) for c in cols]  # type: ignore

            cols.append(col)

            # validate
            tmp = TableSchema(table_name=self.table_name_var.get().strip(), columns=cols, seed=int(self.seed_var.get().strip()))
            validate_schema(tmp)

            self.schema = tmp

            self.col_name_var.set("")
            self.col_min_var.set("")
            self.col_max_var.set("")
            self.col_choices_var.set("")
            self.col_pattern_var.set("")
            self.col_pk_var.set(False)

            self._refresh_columns_table()
            self.status_var.set("Column added.")
        except Exception as exc:
            messagebox.showerror("Add column failed", str(exc))

    def _remove_selected(self) -> None:
        sel = self.columns_tree.selection()
        if not sel:
            return
        idx = int(self.columns_tree.item(sel[0], "tags")[0])
        cols = list(self.schema.columns)
        cols.pop(idx)
        self.schema = TableSchema(table_name=self.schema.table_name, columns=cols, seed=self.schema.seed)
        self._refresh_columns_table()
        self.status_var.set("Column removed.")

    def _move_selected(self, delta: int) -> None:
        sel = self.columns_tree.selection()
        if not sel:
            return
        idx = int(self.columns_tree.item(sel[0], "tags")[0])
        new_idx = idx + delta
        cols = list(self.schema.columns)
        if new_idx < 0 or new_idx >= len(cols):
            return
        cols[idx], cols[new_idx] = cols[new_idx], cols[idx]
        self.schema = TableSchema(table_name=self.schema.table_name, columns=cols, seed=self.schema.seed)
        self._refresh_columns_table()
        # reselect moved row
        self.columns_tree.selection_set(self.columns_tree.get_children()[new_idx])

    def _refresh_columns_table(self) -> None:
        for item in self.columns_tree.get_children():
            self.columns_tree.delete(item)

        for i, c in enumerate(self.schema.columns):
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

    # ---------- Save/Load ----------
    def _save_schema(self) -> None:
        try:
            schema = self._current_schema()
            validate_schema(schema)

            path = filedialog.asksaveasfilename(
                title="Save schema as JSON",
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            save_schema_to_json(schema, path)
            self.status_var.set(f"Saved schema: {path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def _load_schema(self) -> None:
        try:
            path = filedialog.askopenfilename(
                title="Load schema JSON",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            schema = load_schema_from_json(path)
            self.schema = schema
            self.table_name_var.set(schema.table_name)
            self.seed_var.set(str(schema.seed))
            self._refresh_columns_table()
            self.status_var.set(f"Loaded schema: {path}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))

    def _browse_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose SQLite database file",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path_var.set(path)

    # ---------- Preview + Export ----------
    def _refresh_ui_state(self) -> None:
        pass  # placeholder for future centralization

    def _on_preview(self) -> None:
        if self.is_running:
            return
        try:
            schema = self._current_schema()
            validate_schema(schema)
            n = int(self.preview_n_var.get().strip())
            if n <= 0:
                raise ValueError("Preview rows must be > 0.")
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.is_running = True
        self.progress.start(10)
        self.status_var.set("Generating preview…")

        def work():
            try:
                rows = generate_rows(schema, n)
                self.after(0, lambda: self._preview_done(rows))
            except Exception as exc:
                logger.exception("Preview failed: %s", exc)
                self.after(0, lambda: self._job_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _preview_done(self, rows: list[dict[str, object]]) -> None:
        self.preview_rows = rows
        self.progress.stop()
        self.is_running = False
        self.status_var.set(f"Preview generated ({len(rows)} rows).")
        messagebox.showinfo("Preview ready", "Preview generated. You can export to CSV or insert into SQLite.")

    def _export_preview(self) -> None:
        if not self.preview_rows:
            messagebox.showwarning("No preview", "Generate a preview first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export preview to CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            import csv
            cols = [c.name for c in self.schema.columns]
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in self.preview_rows:
                    w.writerow([r.get(c) for c in cols])

            self.status_var.set(f"Exported preview: {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    # ---------- Create + Insert ----------
    def _on_insert(self) -> None:
        if self.is_running:
            return
        try:
            schema = self._current_schema()
            validate_schema(schema)
            db_path = self.db_path_var.get().strip()
            if not db_path:
                raise ValueError("DB path cannot be empty.")
            n = int(self.insert_n_var.get().strip())
            if n <= 0:
                raise ValueError("Insert rows must be > 0.")
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.is_running = True
        self.progress.start(10)
        self.status_var.set("Creating table + generating + inserting…")

        def work():
            try:
                create_table_from_schema(db_path, schema)
                rows = generate_rows(schema, n)
                inserted = insert_rows(db_path, schema, rows, chunk_size=5000)
                self.after(0, lambda: self._insert_done(inserted))
            except Exception as exc:
                logger.exception("Insert failed: %s", exc)
                self.after(0, lambda: self._job_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _insert_done(self, inserted: int) -> None:
        self.progress.stop()
        self.is_running = False
        self.status_var.set(f"Inserted {inserted} rows into SQLite.")
        messagebox.showinfo("Done", f"Inserted {inserted} rows.")

    def _job_failed(self, msg: str) -> None:
        self.progress.stop()
        self.is_running = False
        self.status_var.set("Failed.")
        messagebox.showerror("Error", msg)
