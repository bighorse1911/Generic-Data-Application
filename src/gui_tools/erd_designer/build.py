from __future__ import annotations

def __init__(
        self,
        parent: tk.Widget,
        app: object,
        cfg: AppConfig,
        *,
        show_header: bool = True,
        title_text: str = "ERD Designer",
    ) -> None:
        ttk.Frame.__init__(self, parent, padding=16)
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
