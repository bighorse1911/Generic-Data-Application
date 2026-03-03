from __future__ import annotations

def build_columns_panel(self) -> CollapsiblePanel:
    panel = CollapsiblePanel(self.schema_tab, "Columns", collapsed=False)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    self.columns_panel = panel
    panel.body.columnconfigure(0, weight=1)

    table_editor = ttk.LabelFrame(panel.body, text="Table editor", padding=10)
    table_editor.grid(row=0, column=0, sticky="ew")
    table_editor.columnconfigure(1, weight=1)

    ttk.Label(table_editor, text="Table name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    self.table_name_entry = ttk.Entry(table_editor, textvariable=self.table_name_var)
    self.table_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

    ttk.Label(table_editor, text="Row count (0 for child auto-size):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
    self.row_count_entry = ttk.Entry(table_editor, textvariable=self.row_count_var, width=12)
    self.row_count_entry.grid(row=1, column=1, sticky="w", padx=6, pady=4)

    self.table_mode_medium_group = ttk.LabelFrame(table_editor, text="Medium mode table settings", padding=8)
    self.table_mode_medium_group.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 4))
    self.table_mode_medium_group.columnconfigure(1, weight=1)

    ttk.Label(self.table_mode_medium_group, text="Unique business keys (optional):").grid(
        row=0, column=0, sticky="w", padx=4, pady=3
    )
    self.table_business_key_unique_count_entry = ttk.Entry(
        self.table_mode_medium_group,
        textvariable=self.table_business_key_unique_count_var,
        width=12,
    )
    self.table_business_key_unique_count_entry.grid(row=0, column=1, sticky="w", padx=4, pady=3)

    ttk.Label(self.table_mode_medium_group, text="Business key columns (comma):").grid(
        row=1, column=0, sticky="w", padx=4, pady=3
    )
    self.table_business_key_entry = ttk.Entry(
        self.table_mode_medium_group,
        textvariable=self.table_business_key_var,
    )
    self.table_business_key_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.table_mode_medium_group, text="Business key static columns (comma):").grid(
        row=2, column=0, sticky="w", padx=4, pady=3
    )
    self.table_business_key_static_entry = ttk.Entry(
        self.table_mode_medium_group,
        textvariable=self.table_business_key_static_columns_var,
    )
    self.table_business_key_static_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.table_mode_medium_group, text="Business key changing columns (comma):").grid(
        row=3, column=0, sticky="w", padx=4, pady=3
    )
    self.table_business_key_changing_entry = ttk.Entry(
        self.table_mode_medium_group,
        textvariable=self.table_business_key_changing_columns_var,
    )
    self.table_business_key_changing_entry.grid(row=3, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.table_mode_medium_group, text="SCD mode:").grid(row=4, column=0, sticky="w", padx=4, pady=3)
    self.table_scd_mode_combo = ttk.Combobox(
        self.table_mode_medium_group,
        values=SCD_MODES,
        textvariable=self.table_scd_mode_var,
        state="readonly",
        width=14,
    )
    self.table_scd_mode_combo.grid(row=4, column=1, sticky="w", padx=4, pady=3)

    self.table_mode_complex_group = ttk.LabelFrame(table_editor, text="Complex mode table settings", padding=8)
    self.table_mode_complex_group.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 4))
    self.table_mode_complex_group.columnconfigure(1, weight=1)

    ttk.Label(self.table_mode_complex_group, text="SCD tracked columns (comma):").grid(
        row=0, column=0, sticky="w", padx=4, pady=3
    )
    self.table_scd_tracked_entry = ttk.Entry(
        self.table_mode_complex_group,
        textvariable=self.table_scd_tracked_columns_var,
    )
    self.table_scd_tracked_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.table_mode_complex_group, text="SCD active from column:").grid(
        row=1, column=0, sticky="w", padx=4, pady=3
    )
    self.table_scd_active_from_entry = ttk.Entry(
        self.table_mode_complex_group,
        textvariable=self.table_scd_active_from_var,
    )
    self.table_scd_active_from_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.table_mode_complex_group, text="SCD active to column:").grid(
        row=2, column=0, sticky="w", padx=4, pady=3
    )
    self.table_scd_active_to_entry = ttk.Entry(
        self.table_mode_complex_group,
        textvariable=self.table_scd_active_to_var,
    )
    self.table_scd_active_to_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.table_mode_complex_group, text="Correlation groups JSON (optional):").grid(
        row=3, column=0, sticky="w", padx=4, pady=3
    )
    self.table_correlation_groups_entry = ttk.Entry(
        self.table_mode_complex_group,
        textvariable=self.table_correlation_groups_var,
    )
    self.table_correlation_groups_entry.grid(row=3, column=1, sticky="ew", padx=4, pady=3)
    self.table_correlation_groups_editor_btn = ttk.Button(
        self.table_mode_complex_group,
        text="Open correlation groups JSON editor",
        command=self._open_table_correlation_groups_editor,
    )
    self.table_correlation_groups_editor_btn.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 0))

    self.apply_table_btn = ttk.Button(table_editor, text="Apply table changes", command=self._apply_table_changes)
    self.apply_table_btn.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 0))

    col_editor = ttk.LabelFrame(panel.body, text="Column editor", padding=10)
    col_editor.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    col_editor.columnconfigure(1, weight=1)
    col_editor.columnconfigure(3, weight=1)

    ttk.Label(col_editor, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    self.col_name_entry = ttk.Entry(col_editor, textvariable=self.col_name_var)
    self.col_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
    ttk.Label(col_editor, text="Type:").grid(row=0, column=2, sticky="w", padx=6, pady=4)
    self.col_dtype_combo = ttk.Combobox(
        col_editor,
        values=DTYPES,
        textvariable=self.col_dtype_var,
        state="readonly",
        width=12,
    )
    self.col_dtype_combo.grid(row=0, column=3, sticky="w", padx=6, pady=4)

    self.col_nullable_chk = ttk.Checkbutton(col_editor, text="Nullable", variable=self.col_nullable_var)
    self.col_nullable_chk.grid(row=1, column=0, sticky="w", padx=6, pady=4)
    self.col_pk_chk = ttk.Checkbutton(col_editor, text="Primary key (int only)", variable=self.col_pk_var)
    self.col_pk_chk.grid(row=1, column=1, sticky="w", padx=6, pady=4)
    self.col_unique_chk = ttk.Checkbutton(col_editor, text="Unique", variable=self.col_unique_var)
    self.col_unique_chk.grid(row=1, column=2, sticky="w", padx=6, pady=4)

    ttk.Label(col_editor, text="Min:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
    self.col_min_entry = ttk.Entry(col_editor, textvariable=self.col_min_var, width=12)
    self.col_min_entry.grid(row=2, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(col_editor, text="Max:").grid(row=2, column=2, sticky="w", padx=6, pady=4)
    self.col_max_entry = ttk.Entry(col_editor, textvariable=self.col_max_var, width=12)
    self.col_max_entry.grid(row=2, column=3, sticky="w", padx=6, pady=4)

    ttk.Label(col_editor, text="Choices (comma):").grid(row=3, column=0, sticky="w", padx=6, pady=4)
    self.col_choices_entry = ttk.Entry(col_editor, textvariable=self.col_choices_var)
    self.col_choices_entry.grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

    ttk.Label(col_editor, text="Regex pattern:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
    self.col_pattern_entry = ttk.Entry(col_editor, textvariable=self.col_pattern_var)
    self.col_pattern_entry.grid(row=4, column=1, sticky="ew", padx=6, pady=4)
    self.col_pattern_entry.bind("<FocusOut>", self._on_pattern_entry_focus_out)
    ttk.Label(col_editor, text="Pattern preset:").grid(row=4, column=2, sticky="w", padx=6, pady=4)
    self.col_pattern_preset_combo = ttk.Combobox(
        col_editor,
        values=list(PATTERN_PRESETS.keys()),
        textvariable=self.col_pattern_preset_var,
        state="readonly",
    )
    self.col_pattern_preset_combo.grid(row=4, column=3, sticky="ew", padx=6, pady=4)
    self.col_pattern_preset_combo.bind("<<ComboboxSelected>>", self._on_pattern_preset_selected)

    ttk.Label(col_editor, text="Generator:").grid(row=5, column=0, sticky="w", padx=6, pady=4)
    self.col_generator_combo = ttk.Combobox(
        col_editor,
        values=GENERATORS,
        textvariable=self.col_generator_var,
        state="readonly",
    )
    self.col_generator_combo.grid(row=5, column=1, sticky="ew", padx=6, pady=4)
    ttk.Label(col_editor, text="Params (JSON):").grid(row=5, column=2, sticky="w", padx=6, pady=4)
    self.col_params_entry = ttk.Entry(col_editor, textvariable=self.col_params_var)
    self.col_params_entry.grid(row=5, column=3, sticky="ew", padx=6, pady=4)

    self.columns_mode_medium_group = ttk.Frame(col_editor)
    self.columns_mode_medium_group.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(4, 0))
    self.columns_mode_medium_group.columnconfigure(1, weight=1)
    ttk.Label(self.columns_mode_medium_group, text="Depends on (comma):").grid(
        row=0, column=0, sticky="w", padx=6, pady=4
    )
    self.col_depends_entry = ttk.Entry(self.columns_mode_medium_group, textvariable=self.col_depends_var)
    self.col_depends_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
    self.col_params_template_btn = ttk.Button(
        self.columns_mode_medium_group,
        text="Fill params template for selected generator",
        command=self._apply_generator_params_template,
    )
    self.col_params_template_btn.grid(row=1, column=0, sticky="ew", padx=6, pady=4)
    self.col_params_editor_btn = ttk.Button(
        self.columns_mode_medium_group,
        text="Open params JSON editor",
        command=self._open_params_json_editor,
    )
    self.col_params_editor_btn.grid(row=1, column=1, sticky="ew", padx=6, pady=4)

    action_row = ttk.Frame(col_editor)
    action_row.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(8, 0))
    action_row.columnconfigure(0, weight=1)
    action_row.columnconfigure(1, weight=1)
    action_row.columnconfigure(2, weight=1)
    action_row.columnconfigure(3, weight=1)
    self.add_col_btn = ttk.Button(action_row, text="Add column to selected table", command=self._add_column)
    self.add_col_btn.grid(row=0, column=0, sticky="ew", padx=4)
    self.edit_col_btn = ttk.Button(
        action_row,
        text="Apply edits to selected column",
        command=self._apply_selected_column_changes,
    )
    self.edit_col_btn.grid(row=0, column=1, sticky="ew", padx=4)
    ttk.Button(action_row, text="Move up", command=self._move_column_up).grid(row=0, column=2, sticky="ew", padx=4)
    ttk.Button(action_row, text="Move down", command=self._move_column_down).grid(row=0, column=3, sticky="ew", padx=4)
    ttk.Button(action_row, text="Remove selected column", command=self._remove_selected_column).grid(
        row=1, column=0, columnspan=4, sticky="ew", padx=4, pady=(6, 0)
    )

    cols_frame = ttk.LabelFrame(panel.body, text="Columns", padding=8)
    cols_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
    cols_frame.columnconfigure(0, weight=1)
    cols_frame.rowconfigure(1, weight=1)

    self.columns_search = SearchEntry(
        cols_frame,
        on_change=self._on_columns_search_change,
        delay_ms=VALIDATION_DEBOUNCE_MS,
    )
    self.columns_search.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))

    cols = ("name", "dtype", "nullable", "pk", "unique", "min", "max", "choices", "pattern")
    self.columns_tree = ttk.Treeview(cols_frame, columns=cols, show="headings", height=10)
    for col_name in cols:
        self.columns_tree.heading(col_name, text=col_name)
        self.columns_tree.column(col_name, width=110, anchor="w", stretch=True)
    self.columns_tree.column("name", width=160)
    self.columns_tree.column("choices", width=180)
    self.columns_tree.column("pattern", width=180)
    self.columns_tree.grid(row=1, column=0, sticky="nsew")
    self.columns_tree.bind("<<TreeviewSelect>>", self._on_column_selected)
    yscroll = ttk.Scrollbar(cols_frame, orient="vertical", command=self.columns_tree.yview)
    yscroll.grid(row=1, column=1, sticky="ns")
    self.columns_tree.configure(yscrollcommand=yscroll.set)

    paging = ttk.Frame(cols_frame)
    paging.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
    self.columns_page_var = tk.StringVar(value="No matching columns.")
    ttk.Label(paging, textvariable=self.columns_page_var).pack(side="left")
    self.columns_prev_btn = ttk.Button(paging, text="Prev", command=self._on_columns_filter_prev_page)
    self.columns_prev_btn.pack(side="right")
    self.columns_next_btn = ttk.Button(paging, text="Next", command=self._on_columns_filter_next_page)
    self.columns_next_btn.pack(side="right", padx=(0, 6))
    return panel


