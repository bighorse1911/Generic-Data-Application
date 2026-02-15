import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.erd_designer import (
    ERD_AUTHORING_DTYPES,
    add_column_to_erd_project,
    add_relationship_to_erd_project,
    add_table_to_erd_project,
    apply_node_position_overrides,
    build_erd_layout,
    build_erd_svg,
    compute_diagram_size,
    edge_label,
    export_schema_project_to_json,
    export_erd_file,
    load_project_schema_for_erd,
    new_erd_schema_project,
    node_anchor_y,
    table_for_edge,
    update_column_in_erd_project,
    update_table_in_erd_project,
)
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog

class ERDDesignerToolFrame(ttk.Frame):
    """Schema-to-diagram view for table/column/FK relationship inspection."""
    ERROR_SURFACE_CONTEXT = "ERD designer"
    ERROR_DIALOG_TITLE = "ERD designer error"
    WARNING_DIALOG_TITLE = "ERD designer warning"

    def __init__(
        self,
        parent: tk.Widget,
        app: object,
        cfg: AppConfig,
        *,
        show_header: bool = True,
        title_text: str = "ERD Designer",
    ) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._last_diagram_width = 1200
        self._last_diagram_height = 800
        self._node_positions: dict[str, tuple[int, int]] = {}
        self._node_bounds: dict[str, tuple[int, int, int, int]] = {}
        self._node_draw_order: list[str] = []
        self._drag_table_name: str | None = None
        self._drag_offset: tuple[float, float] | None = None

        self.schema_path_var = tk.StringVar(value="")
        self.show_relationships_var = tk.BooleanVar(value=True)
        self.show_columns_var = tk.BooleanVar(value=True)
        self.show_dtypes_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Load a project schema JSON file to render ERD.")
        self.schema_name_var = tk.StringVar(value="new_schema_project")
        self.schema_seed_var = tk.StringVar(value=str(cfg.seed))
        self.table_name_var = tk.StringVar(value="")
        self.table_row_count_var = tk.StringVar(value="100")
        self.column_table_var = tk.StringVar(value="")
        self.column_name_var = tk.StringVar(value="")
        self.column_dtype_var = tk.StringVar(value=ERD_AUTHORING_DTYPES[0])
        self.column_primary_key_var = tk.BooleanVar(value=False)
        self.column_nullable_var = tk.BooleanVar(value=True)
        self.relationship_child_table_var = tk.StringVar(value="")
        self.relationship_child_column_var = tk.StringVar(value="")
        self.relationship_parent_table_var = tk.StringVar(value="")
        self.relationship_parent_column_var = tk.StringVar(value="")
        self.relationship_min_children_var = tk.StringVar(value="1")
        self.relationship_max_children_var = tk.StringVar(value="3")
        self.edit_table_current_var = tk.StringVar(value="")
        self.edit_table_name_var = tk.StringVar(value="")
        self.edit_table_row_count_var = tk.StringVar(value="100")
        self.edit_column_table_var = tk.StringVar(value="")
        self.edit_column_current_var = tk.StringVar(value="")
        self.edit_column_name_var = tk.StringVar(value="")
        self.edit_column_dtype_var = tk.StringVar(value=ERD_AUTHORING_DTYPES[0])
        self.edit_column_primary_key_var = tk.BooleanVar(value=False)
        self.edit_column_nullable_var = tk.BooleanVar(value=True)
        self._authoring_collapsed = False
        self.error_surface = ErrorSurface(
            context=self.ERROR_SURFACE_CONTEXT,
            dialog_title=self.ERROR_DIALOG_TITLE,
            warning_title=self.WARNING_DIALOG_TITLE,
            show_dialog=show_error_dialog,
            show_warning=show_warning_dialog,
            set_status=self.status_var.set,
        )

        if show_header:
            header = ttk.Frame(self)
            header.pack(fill="x", pady=(0, 8))
            ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
            ttk.Label(header, text=title_text, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=940,
            text=(
                "Load a schema project JSON or create a new schema directly on this page. "
                "Toggle relationships, column names, and datatypes for different views. "
                "Drag table cards to rearrange layout."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        controls = ttk.LabelFrame(self, text="Input + display options", padding=8)
        controls.pack(fill="x", pady=(0, 8))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Schema project JSON").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.schema_path_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(controls, text="Browse...", command=self._browse_schema_path).grid(row=0, column=2, sticky="ew")
        ttk.Button(controls, text="Render ERD", command=self._load_and_render).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(8, 0),
        )
        ttk.Button(controls, text="Export ERD...", command=self._export_erd).grid(
            row=0,
            column=4,
            sticky="ew",
            padx=(8, 0),
        )
        ttk.Button(controls, text="Export schema JSON...", command=self._export_schema_json).grid(
            row=0,
            column=5,
            sticky="ew",
            padx=(8, 0),
        )

        options = ttk.Frame(controls)
        options.grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            options,
            text="Show relationships",
            variable=self.show_relationships_var,
            command=self._on_options_changed,
        ).pack(side="left")
        ttk.Checkbutton(
            options,
            text="Show column names",
            variable=self.show_columns_var,
            command=self._on_options_changed,
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            options,
            text="Show datatypes",
            variable=self.show_dtypes_var,
            command=self._on_options_changed,
        ).pack(side="left", padx=(12, 0))
        self.authoring_toggle_btn = ttk.Button(
            options,
            text="Collapse schema authoring",
            command=self._toggle_authoring_panel,
        )
        self.authoring_toggle_btn.pack(side="left", padx=(16, 0))

        self.authoring_box = ttk.LabelFrame(self, text="Schema authoring", padding=8)
        self.authoring_box.pack(fill="x", pady=(0, 8))

        schema_row = ttk.Frame(self.authoring_box)
        schema_row.pack(fill="x", pady=(0, 6))
        ttk.Label(schema_row, text="Schema name").pack(side="left")
        ttk.Entry(schema_row, textvariable=self.schema_name_var, width=24).pack(side="left", padx=(8, 12))
        ttk.Label(schema_row, text="Seed").pack(side="left")
        ttk.Entry(schema_row, textvariable=self.schema_seed_var, width=10).pack(side="left", padx=(8, 12))
        ttk.Button(schema_row, text="Create new schema", command=self._create_new_schema).pack(side="left")

        table_row = ttk.Frame(self.authoring_box)
        table_row.pack(fill="x", pady=(0, 6))
        ttk.Label(table_row, text="Table (blank = new)").pack(side="left")
        self.edit_table_current_combo = ttk.Combobox(
            table_row,
            textvariable=self.edit_table_current_var,
            state="readonly",
            width=20,
            values=(),
        )
        self.edit_table_current_combo.pack(side="left", padx=(8, 8))
        self.edit_table_current_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_edit_table_selected())
        ttk.Label(table_row, text="Name").pack(side="left")
        ttk.Entry(table_row, textvariable=self.edit_table_name_var, width=20).pack(side="left", padx=(8, 8))
        ttk.Label(table_row, text="Row count").pack(side="left")
        ttk.Entry(table_row, textvariable=self.edit_table_row_count_var, width=8).pack(side="left", padx=(8, 8))
        ttk.Button(table_row, text="Save table", command=self._save_table_shared).pack(side="left", padx=(8, 4))
        ttk.Button(table_row, text="New table", command=self._reset_table_editor).pack(side="left")

        column_row = ttk.Frame(self.authoring_box)
        column_row.pack(fill="x", pady=(0, 6))
        ttk.Label(column_row, text="Column table").pack(side="left")
        self.edit_column_table_combo = ttk.Combobox(
            column_row,
            textvariable=self.edit_column_table_var,
            state="readonly",
            width=16,
            values=(),
        )
        self.edit_column_table_combo.pack(side="left", padx=(8, 8))
        self.edit_column_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_edit_column_table_changed(),
        )
        ttk.Label(column_row, text="Column (blank = new)").pack(side="left")
        self.edit_column_current_combo = ttk.Combobox(
            column_row,
            textvariable=self.edit_column_current_var,
            state="readonly",
            width=18,
            values=(),
        )
        self.edit_column_current_combo.pack(side="left", padx=(8, 8))
        self.edit_column_current_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_edit_column_selected(),
        )
        ttk.Label(column_row, text="Name").pack(side="left")
        ttk.Entry(column_row, textvariable=self.edit_column_name_var, width=16).pack(side="left", padx=(8, 8))
        ttk.Label(column_row, text="DType").pack(side="left")
        self.edit_column_dtype_combo = ttk.Combobox(
            column_row,
            textvariable=self.edit_column_dtype_var,
            state="readonly",
            width=8,
            values=ERD_AUTHORING_DTYPES,
        )
        self.edit_column_dtype_combo.pack(side="left", padx=(8, 8))
        ttk.Checkbutton(
            column_row,
            text="Primary key",
            variable=self.edit_column_primary_key_var,
            command=self._on_edit_column_pk_changed,
        ).pack(side="left")
        self.edit_column_nullable_check = ttk.Checkbutton(
            column_row,
            text="Nullable",
            variable=self.edit_column_nullable_var,
        )
        self.edit_column_nullable_check.pack(side="left", padx=(8, 8))
        ttk.Button(column_row, text="Save column", command=self._save_column_shared).pack(side="left", padx=(8, 4))
        ttk.Button(column_row, text="New column", command=self._reset_column_editor).pack(side="left")

        relationship_row = ttk.Frame(self.authoring_box)
        relationship_row.pack(fill="x")
        ttk.Label(relationship_row, text="Child table").pack(side="left")
        self.relationship_child_table_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_child_table_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_child_table_combo.pack(side="left", padx=(8, 8))
        self.relationship_child_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_relationship_child_table_changed(),
        )
        ttk.Label(relationship_row, text="Child column").pack(side="left")
        self.relationship_child_column_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_child_column_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_child_column_combo.pack(side="left", padx=(8, 8))
        ttk.Label(relationship_row, text="Parent table").pack(side="left")
        self.relationship_parent_table_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_parent_table_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_parent_table_combo.pack(side="left", padx=(8, 8))
        self.relationship_parent_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_relationship_parent_table_changed(),
        )
        ttk.Label(relationship_row, text="Parent column").pack(side="left")
        self.relationship_parent_column_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_parent_column_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_parent_column_combo.pack(side="left", padx=(8, 8))
        ttk.Label(relationship_row, text="Min").pack(side="left")
        ttk.Entry(relationship_row, textvariable=self.relationship_min_children_var, width=5).pack(side="left", padx=(6, 4))
        ttk.Label(relationship_row, text="Max").pack(side="left")
        ttk.Entry(relationship_row, textvariable=self.relationship_max_children_var, width=5).pack(side="left", padx=(6, 8))
        ttk.Button(relationship_row, text="Add relationship", command=self._add_relationship).pack(side="left")

        self.diagram_box = ttk.LabelFrame(self, text="ERD preview", padding=8)
        self.diagram_box.pack(fill="both", expand=True)
        self.diagram_box.columnconfigure(0, weight=1)
        self.diagram_box.rowconfigure(0, weight=1)

        self.erd_canvas = tk.Canvas(self.diagram_box, background="#f3f6fb", highlightthickness=1, highlightbackground="#a8b7cc")
        self.erd_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(self.diagram_box, orient="vertical", command=self.erd_canvas.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(self.diagram_box, orient="horizontal", command=self.erd_canvas.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.erd_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.erd_canvas.bind("<Configure>", lambda _event: self._draw_erd())
        self.erd_canvas.bind("<ButtonPress-1>", self._on_erd_drag_start)
        self.erd_canvas.bind("<B1-Motion>", self._on_erd_drag_motion)
        self.erd_canvas.bind("<ButtonRelease-1>", self._on_erd_drag_end)

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))
        self._on_column_pk_changed()
        self._on_edit_column_pk_changed()
        self._sync_authoring_controls_from_project()

    def _erd_error(self, field: str, issue: str, hint: str) -> str:
        return f"ERD Designer / {field}: {issue}. Fix: {hint}."

    def _show_error_dialog(self, location: str, message: object) -> str:
        return self.error_surface.emit_exception_actionable(
            message,
            location=(str(location).strip() or "ERD designer"),
            hint="review the inputs and retry",
            mode="mixed",
        )

    def _browse_schema_path(self) -> None:
        path = filedialog.askopenfilename(
            title="Select schema project JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path == "":
            return
        self.schema_path_var.set(path)

    def _toggle_authoring_panel(self) -> None:
        self._authoring_collapsed = not self._authoring_collapsed
        if self._authoring_collapsed:
            self.authoring_box.pack_forget()
            self.authoring_toggle_btn.configure(text="Expand schema authoring")
            return
        self.authoring_box.pack(fill="x", pady=(0, 8), before=self.diagram_box)
        self.authoring_toggle_btn.configure(text="Collapse schema authoring")

    def _set_combo_values(
        self,
        combo: ttk.Combobox,
        *,
        values: list[str],
        variable: tk.StringVar,
    ) -> None:
        combo.configure(values=tuple(values))
        current = variable.get().strip()
        if current in values:
            variable.set(current)
            return
        if values:
            variable.set(values[0])
            return
        variable.set("")

    def _table_names(self) -> list[str]:
        if self.project is None:
            return []
        return [table.table_name for table in self.project.tables]

    def _table_for_name(self, table_name: str) -> object | None:
        if self.project is None:
            return None
        for table in self.project.tables:
            if table.table_name == table_name:
                return table
        return None

    def _columns_for_table(self, table_name: str, *, primary_key_only: bool = False) -> list[str]:
        if self.project is None:
            return []
        for table in self.project.tables:
            if table.table_name != table_name:
                continue
            if primary_key_only:
                return [column.name for column in table.columns if column.primary_key]
            return [column.name for column in table.columns]
        return []

    def _sync_authoring_controls_from_project(self) -> None:
        table_names = self._table_names()
        self._set_combo_values(
            self.relationship_child_table_combo,
            values=table_names,
            variable=self.relationship_child_table_var,
        )
        self._set_combo_values(
            self.relationship_parent_table_combo,
            values=table_names,
            variable=self.relationship_parent_table_var,
        )
        self._set_combo_values(
            self.edit_table_current_combo,
            values=["", *table_names],
            variable=self.edit_table_current_var,
        )
        self._set_combo_values(
            self.edit_column_table_combo,
            values=table_names,
            variable=self.edit_column_table_var,
        )
        self.column_table_var.set(self.edit_column_table_var.get().strip())
        self._on_column_table_changed()
        self._on_relationship_child_table_changed()
        self._on_relationship_parent_table_changed()
        self._on_edit_table_selected()
        self._on_edit_column_table_changed()

    def _on_column_pk_changed(self) -> None:
        if not hasattr(self, "column_nullable_check"):
            return
        if self.column_primary_key_var.get():
            self.column_nullable_var.set(False)
            self.column_nullable_check.state(["disabled"])
            return
        self.column_nullable_check.state(["!disabled"])

    def _on_column_table_changed(self) -> None:
        # Selection is intentionally retained; no dependent widgets currently require sync.
        _ = self.column_table_var.get().strip()

    def _on_edit_table_selected(self) -> None:
        table_name = self.edit_table_current_var.get().strip()
        table = self._table_for_name(table_name)
        if table is None:
            if table_name == "":
                self.edit_table_name_var.set("")
            self.edit_table_row_count_var.set("100")
            return
        self.edit_table_name_var.set(table.table_name)
        self.edit_table_row_count_var.set(str(table.row_count))

    def _on_edit_column_table_changed(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        column_names = self._columns_for_table(table_name)
        self._set_combo_values(
            self.edit_column_current_combo,
            values=["", *column_names],
            variable=self.edit_column_current_var,
        )
        self._on_edit_column_selected()

    def _on_edit_column_selected(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        column_name = self.edit_column_current_var.get().strip()
        table = self._table_for_name(table_name)
        if table is None or not column_name:
            self.edit_column_name_var.set("")
            self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
            self.edit_column_primary_key_var.set(False)
            self.edit_column_nullable_var.set(True)
            self._on_edit_column_pk_changed()
            return
        selected_column = None
        for column in table.columns:
            if column.name == column_name:
                selected_column = column
                break
        if selected_column is None:
            self.edit_column_name_var.set("")
            self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
            self.edit_column_primary_key_var.set(False)
            self.edit_column_nullable_var.set(True)
            self._on_edit_column_pk_changed()
            return
        self.edit_column_name_var.set(selected_column.name)
        dtype = selected_column.dtype
        if dtype == "float":
            dtype = "decimal"
        if dtype not in ERD_AUTHORING_DTYPES:
            dtype = ERD_AUTHORING_DTYPES[0]
        self.edit_column_dtype_var.set(dtype)
        self.edit_column_primary_key_var.set(bool(selected_column.primary_key))
        self.edit_column_nullable_var.set(bool(selected_column.nullable))
        self._on_edit_column_pk_changed()

    def _on_edit_column_pk_changed(self) -> None:
        if not hasattr(self, "edit_column_nullable_check"):
            return
        if self.edit_column_primary_key_var.get():
            self.edit_column_nullable_var.set(False)
            self.edit_column_nullable_check.state(["disabled"])
            return
        self.edit_column_nullable_check.state(["!disabled"])

    def _reset_table_editor(self) -> None:
        self.edit_table_current_var.set("")
        self.edit_table_name_var.set("")
        self.edit_table_row_count_var.set("100")

    def _reset_column_editor(self) -> None:
        self.edit_column_current_var.set("")
        self.edit_column_name_var.set("")
        self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
        self.edit_column_primary_key_var.set(False)
        self.edit_column_nullable_var.set(True)
        self._on_edit_column_pk_changed()

    def _save_table_shared(self) -> None:
        current_table_name = self.edit_table_current_var.get().strip()
        new_table_name = self.edit_table_name_var.get().strip()
        try:
            if current_table_name == "":
                self.project = add_table_to_erd_project(
                    self.project,
                    table_name_value=new_table_name,
                    row_count_value=self.edit_table_row_count_var.get(),
                )
                if self.project is None:
                    return
                self.table_name_var.set(new_table_name)
                self.table_row_count_var.set(self.edit_table_row_count_var.get())
                self.edit_table_current_var.set(new_table_name)
                status_text = f"Added table '{new_table_name}'."
            else:
                self.project = update_table_in_erd_project(
                    self.project,
                    current_table_name_value=current_table_name,
                    new_table_name_value=new_table_name,
                    row_count_value=self.edit_table_row_count_var.get(),
                )
                if current_table_name != new_table_name and current_table_name in self._node_positions:
                    self._node_positions[new_table_name] = self._node_positions.pop(current_table_name)
                self.edit_table_current_var.set(new_table_name)
                status_text = f"Updated table '{current_table_name}' -> '{new_table_name}'."
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(status_text)

    def _save_column_shared(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        current_column_name = self.edit_column_current_var.get().strip()
        new_column_name = self.edit_column_name_var.get().strip()
        self.column_table_var.set(table_name)
        self.column_name_var.set(new_column_name)
        self.column_dtype_var.set(self.edit_column_dtype_var.get())
        self.column_primary_key_var.set(bool(self.edit_column_primary_key_var.get()))
        self.column_nullable_var.set(bool(self.edit_column_nullable_var.get()))
        try:
            if current_column_name == "":
                self.project = add_column_to_erd_project(
                    self.project,
                    table_name_value=table_name,
                    column_name_value=new_column_name,
                    dtype_value=self.edit_column_dtype_var.get(),
                    primary_key=bool(self.edit_column_primary_key_var.get()),
                    nullable=bool(self.edit_column_nullable_var.get()),
                )
                self.edit_column_current_var.set(new_column_name)
                status_text = f"Added column '{table_name}.{new_column_name}'."
            else:
                self.project = update_column_in_erd_project(
                    self.project,
                    table_name_value=table_name,
                    current_column_name_value=current_column_name,
                    new_column_name_value=new_column_name,
                    dtype_value=self.edit_column_dtype_var.get(),
                    primary_key=bool(self.edit_column_primary_key_var.get()),
                    nullable=bool(self.edit_column_nullable_var.get()),
                )
                self.edit_column_current_var.set(new_column_name)
                status_text = (
                    f"Updated column '{table_name}.{current_column_name}' -> '{table_name}.{new_column_name}'."
                )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(status_text)

    def _on_relationship_child_table_changed(self) -> None:
        child_columns = self._columns_for_table(self.relationship_child_table_var.get().strip())
        self._set_combo_values(
            self.relationship_child_column_combo,
            values=child_columns,
            variable=self.relationship_child_column_var,
        )

    def _on_relationship_parent_table_changed(self) -> None:
        parent_columns = self._columns_for_table(
            self.relationship_parent_table_var.get().strip(),
            primary_key_only=True,
        )
        self._set_combo_values(
            self.relationship_parent_column_combo,
            values=parent_columns,
            variable=self.relationship_parent_column_var,
        )

    def _create_new_schema(self) -> None:
        try:
            self.project = new_erd_schema_project(
                name_value=self.schema_name_var.get(),
                seed_value=self.schema_seed_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self.schema_path_var.set("")
        self._node_positions = {}
        self._node_bounds = {}
        self._node_draw_order = []
        self._drag_table_name = None
        self._drag_offset = None
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(
            f"Created new schema '{self.project.name}' with seed={self.project.seed}. Add tables, columns, and relationships."
        )

    def _add_table(self) -> None:
        try:
            self.project = add_table_to_erd_project(
                self.project,
                table_name_value=self.table_name_var.get(),
                row_count_value=self.table_row_count_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        table_name = self.table_name_var.get().strip()
        self.table_name_var.set("")
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Added table '{table_name}'.")

    def _edit_table(self) -> None:
        current_table_name = self.edit_table_current_var.get().strip()
        new_table_name = self.edit_table_name_var.get().strip()
        try:
            self.project = update_table_in_erd_project(
                self.project,
                current_table_name_value=current_table_name,
                new_table_name_value=new_table_name,
                row_count_value=self.edit_table_row_count_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        if current_table_name != new_table_name and current_table_name in self._node_positions:
            self._node_positions[new_table_name] = self._node_positions.pop(current_table_name)
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Updated table '{current_table_name}' -> '{new_table_name}'.")

    def _add_column(self) -> None:
        try:
            self.project = add_column_to_erd_project(
                self.project,
                table_name_value=self.column_table_var.get(),
                column_name_value=self.column_name_var.get(),
                dtype_value=self.column_dtype_var.get(),
                primary_key=bool(self.column_primary_key_var.get()),
                nullable=bool(self.column_nullable_var.get()),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        column_name = self.column_name_var.get().strip()
        table_name = self.column_table_var.get().strip()
        self.column_name_var.set("")
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Added column '{table_name}.{column_name}'.")

    def _edit_column(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        current_column_name = self.edit_column_current_var.get().strip()
        new_column_name = self.edit_column_name_var.get().strip()
        try:
            self.project = update_column_in_erd_project(
                self.project,
                table_name_value=table_name,
                current_column_name_value=current_column_name,
                new_column_name_value=new_column_name,
                dtype_value=self.edit_column_dtype_var.get(),
                primary_key=bool(self.edit_column_primary_key_var.get()),
                nullable=bool(self.edit_column_nullable_var.get()),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Updated column '{table_name}.{current_column_name}' -> '{table_name}.{new_column_name}'.")

    def _add_relationship(self) -> None:
        try:
            self.project = add_relationship_to_erd_project(
                self.project,
                child_table_value=self.relationship_child_table_var.get(),
                child_column_value=self.relationship_child_column_var.get(),
                parent_table_value=self.relationship_parent_table_var.get(),
                parent_column_value=self.relationship_parent_column_var.get(),
                min_children_value=self.relationship_min_children_var.get(),
                max_children_value=self.relationship_max_children_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        child_table = self.relationship_child_table_var.get().strip()
        child_column = self.relationship_child_column_var.get().strip()
        parent_table = self.relationship_parent_table_var.get().strip()
        parent_column = self.relationship_parent_column_var.get().strip()
        self._draw_erd()
        self.status_var.set(
            f"Added relationship '{child_table}.{child_column} -> {parent_table}.{parent_column}'."
        )

    def _load_and_render(self) -> None:
        try:
            self.project = load_project_schema_for_erd(self.schema_path_var.get())
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self.schema_name_var.set(self.project.name)
        self.schema_seed_var.set(str(self.project.seed))
        self._node_positions = {}
        self._node_bounds = {}
        self._node_draw_order = []
        self._drag_table_name = None
        self._drag_offset = None
        self._sync_authoring_controls_from_project()
        self._draw_erd()

    def _export_schema_json(self) -> None:
        if self.project is None:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Schema export",
                    "schema is not loaded",
                    "create or load a schema project before exporting JSON",
                ),
            )
            return

        output_path = filedialog.asksaveasfilename(
            title="Export schema project JSON",
            defaultextension=".json",
            initialfile=f"{self.project.name}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.status_var.set("Schema JSON export cancelled.")
            return

        try:
            saved_path = export_schema_project_to_json(
                project=self.project,
                output_path_value=output_path,
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return

        self.schema_path_var.set(str(saved_path))
        self.status_var.set(f"Exported schema JSON to {saved_path}.")

    def _export_erd(self) -> None:
        if self.project is None:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    "ERD is not loaded",
                    "load and render a schema project before exporting",
                ),
            )
            return

        output_path = filedialog.asksaveasfilename(
            title="Export ERD",
            defaultextension=".svg",
            initialfile=f"{self.project.name}_erd.svg",
            filetypes=[
                ("SVG files", "*.svg"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
        )
        if output_path == "":
            self.status_var.set("ERD export cancelled.")
            return

        show_columns = bool(self.show_columns_var.get())
        show_dtypes = bool(self.show_dtypes_var.get()) and show_columns
        ext = Path(output_path).suffix.lower()
        postscript_data: str | None = None

        try:
            svg_text = build_erd_svg(
                self.project,
                show_relationships=bool(self.show_relationships_var.get()),
                show_columns=show_columns,
                show_dtypes=show_dtypes,
                node_positions=self._node_positions,
            )
            if ext in {".png", ".jpg", ".jpeg"}:
                width = max(1, int(self._last_diagram_width))
                height = max(1, int(self._last_diagram_height))
                postscript_data = self.erd_canvas.postscript(
                    colormode="color",
                    x=0,
                    y=0,
                    width=width,
                    height=height,
                    pagewidth=f"{width}p",
                    pageheight=f"{height}p",
                )
            saved_path = export_erd_file(
                output_path_value=output_path,
                svg_text=svg_text,
                postscript_data=postscript_data,
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        except tk.TclError as exc:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    f"failed to capture rendered canvas ({exc})",
                    "render the ERD and retry export",
                ),
            )
            return
        except OSError as exc:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    f"failed to write export file ({exc})",
                    "check write permissions and destination path",
                ),
            )
            return

        self.status_var.set(f"Exported ERD to {saved_path}.")

    def _on_options_changed(self) -> None:
        if not self.show_columns_var.get() and self.show_dtypes_var.get():
            # Datatype-only rows are not meaningful without column names.
            self.show_dtypes_var.set(False)
        self._draw_erd()

    def _draw_erd(self) -> None:
        self.erd_canvas.delete("all")
        if self.project is None:
            self._last_diagram_width = 1200
            self._last_diagram_height = 800
            self._node_bounds = {}
            self._node_draw_order = []
            self.erd_canvas.configure(scrollregion=(0, 0, 1200, 800))
            return

        show_columns = bool(self.show_columns_var.get())
        show_dtypes = bool(self.show_dtypes_var.get()) and show_columns

        base_nodes, edges, diagram_width, diagram_height = build_erd_layout(
            self.project,
            show_columns=show_columns,
            show_dtypes=show_dtypes,
        )
        nodes = apply_node_position_overrides(base_nodes, positions=self._node_positions)
        diagram_width, diagram_height = compute_diagram_size(
            nodes,
            min_width=diagram_width,
            min_height=diagram_height,
        )
        self._last_diagram_width = diagram_width
        self._last_diagram_height = diagram_height
        self.erd_canvas.configure(scrollregion=(0, 0, diagram_width, diagram_height))

        node_by_table = {node.table_name: node for node in nodes}
        table_map = {table.table_name: table for table in self.project.tables}
        self._node_bounds = {}
        self._node_draw_order = []

        for node in nodes:
            x1 = node.x
            y1 = node.y
            x2 = node.x + node.width
            y2 = node.y + node.height
            self._node_bounds[node.table_name] = (x1, y1, x2, y2)
            self._node_draw_order.append(node.table_name)

            self.erd_canvas.create_rectangle(x1, y1, x2, y2, fill="#ffffff", outline="#556b8a", width=2)
            self.erd_canvas.create_rectangle(x1, y1, x2, y1 + 30, fill="#dae7f8", outline="#556b8a", width=2)
            self.erd_canvas.create_text(
                x1 + 8,
                y1 + 15,
                text=node.table_name,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                fill="#1a2a44",
            )

            detail_lines = node.lines if node.lines else ["(columns hidden)"]
            y = y1 + 40
            for line in detail_lines:
                self.erd_canvas.create_text(
                    x1 + 8,
                    y,
                    text=line,
                    anchor="w",
                    font=("Consolas", 9),
                    fill="#27374d",
                )
                y += 18

        if self.show_relationships_var.get():
            for edge in edges:
                parent_node = node_by_table.get(edge.parent_table)
                child_node = node_by_table.get(edge.child_table)
                if parent_node is None or child_node is None:
                    continue
                try:
                    parent_table, child_table = table_for_edge(edge, table_map=table_map)
                except ValueError:
                    continue

                if show_columns:
                    y1 = node_anchor_y(parent_node, table=parent_table, column_name=edge.parent_column)
                    y2 = node_anchor_y(child_node, table=child_table, column_name=edge.child_column)
                else:
                    y1 = int(parent_node.y + parent_node.height / 2)
                    y2 = int(child_node.y + child_node.height / 2)
                x1 = parent_node.x + parent_node.width
                x2 = child_node.x
                mid_x = int((x1 + x2) / 2)

                self.erd_canvas.create_line(
                    x1,
                    y1,
                    mid_x,
                    y1,
                    mid_x,
                    y2,
                    x2,
                    y2,
                    fill="#1f5a95",
                    width=2,
                    arrow=tk.LAST,
                )
                self.erd_canvas.create_text(
                    mid_x + 6,
                    int((y1 + y2) / 2) - 7,
                    text=edge_label(edge),
                    anchor="w",
                    font=("Segoe UI", 8),
                    fill="#1f5a95",
                )

        self.status_var.set(
            f"Rendered ERD for project '{self.project.name}' with {len(nodes)} tables and {len(edges)} relationships."
        )

    def _table_name_at_canvas_point(self, x: float, y: float) -> str | None:
        for table_name in reversed(self._node_draw_order):
            bounds = self._node_bounds.get(table_name)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            if x1 <= x <= x2 and y1 <= y <= y2:
                return table_name
        return None

    def _on_erd_drag_start(self, event: tk.Event) -> None:
        if self.project is None:
            return
        canvas_x = float(self.erd_canvas.canvasx(event.x))
        canvas_y = float(self.erd_canvas.canvasy(event.y))
        table_name = self._table_name_at_canvas_point(canvas_x, canvas_y)
        if table_name is None:
            self._drag_table_name = None
            self._drag_offset = None
            return
        bounds = self._node_bounds.get(table_name)
        if bounds is None:
            return
        self._drag_table_name = table_name
        self._drag_offset = (canvas_x - bounds[0], canvas_y - bounds[1])

    def _on_erd_drag_motion(self, event: tk.Event) -> None:
        if self._drag_table_name is None or self._drag_offset is None:
            return
        canvas_x = float(self.erd_canvas.canvasx(event.x))
        canvas_y = float(self.erd_canvas.canvasy(event.y))
        next_x = max(16, int(canvas_x - self._drag_offset[0]))
        next_y = max(16, int(canvas_y - self._drag_offset[1]))
        self._node_positions[self._drag_table_name] = (next_x, next_y)
        self._draw_erd()

    def _on_erd_drag_end(self, _event: tk.Event) -> None:
        self._drag_table_name = None
        self._drag_offset = None


