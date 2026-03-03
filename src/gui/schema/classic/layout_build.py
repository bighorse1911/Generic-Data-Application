from __future__ import annotations


def _build(self) -> None:
    root = self.scroll.inner

    # =========================
    # Header (pack on root)
    # =========================
    header = ttk.Frame(root)
    header.pack(fill="x", pady=(0, 10))

    ttk.Button(header, text="<- Back", command=self._on_back_requested).pack(side="left")
    ttk.Label(header, text="Schema Project Designer", font=("Segoe UI", 16, "bold")).pack(side="left", padx=12)
    ttk.Label(header, textvariable=self._dirty_indicator_var).pack(side="left")
    ttk.Button(header, text="Notifications", command=self._show_notifications_history).pack(side="right", padx=(6, 0))
    ttk.Button(header, text="Zoom +", command=self.scroll.zoom_in).pack(side="top", padx=0)
    ttk.Button(header, text="Zoom −", command=self.scroll.zoom_out).pack(side="top", padx=0)
    ttk.Button(header, text="Reset", command=self.scroll.reset_zoom).pack(side="top", padx=0)


    # =========================
    # Project bar (grid inside proj)
    # =========================
    proj = ttk.LabelFrame(root, text="Project", padding=12)
    proj.pack(fill="x")

    proj.columnconfigure(1, weight=1)

    ttk.Label(proj, text="Project name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    ttk.Entry(proj, textvariable=self.project_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(proj, text="Seed:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
    ttk.Entry(proj, textvariable=self.seed_var, width=12).grid(row=0, column=3, sticky="w", padx=6, pady=6)

    ttk.Label(proj, text="Timeline constraints JSON (optional):").grid(
        row=1,
        column=0,
        sticky="w",
        padx=6,
        pady=6,
    )
    self.project_timeline_constraints_entry = ttk.Entry(
        proj,
        textvariable=self.project_timeline_constraints_var,
    )
    self.project_timeline_constraints_entry.grid(
        row=1,
        column=1,
        columnspan=3,
        sticky="ew",
        padx=6,
        pady=6,
    )
    self.project_timeline_constraints_editor_btn = ttk.Button(
        proj,
        text="Open timeline constraints JSON editor",
        command=self._open_project_timeline_constraints_editor,
    )
    self.project_timeline_constraints_editor_btn.grid(
        row=2,
        column=0,
        columnspan=4,
        sticky="ew",
        padx=6,
        pady=(0, 6),
    )

    ttk.Label(proj, text="Data quality profiles JSON (optional):").grid(
        row=3,
        column=0,
        sticky="w",
        padx=6,
        pady=6,
    )
    self.project_data_quality_profiles_entry = ttk.Entry(
        proj,
        textvariable=self.project_data_quality_profiles_var,
    )
    self.project_data_quality_profiles_entry.grid(
        row=3,
        column=1,
        columnspan=3,
        sticky="ew",
        padx=6,
        pady=6,
    )
    self.project_data_quality_profiles_editor_btn = ttk.Button(
        proj,
        text="Open data quality profiles JSON editor",
        command=self._open_project_data_quality_profiles_editor,
    )
    self.project_data_quality_profiles_editor_btn.grid(
        row=4,
        column=0,
        columnspan=4,
        sticky="ew",
        padx=6,
        pady=(0, 6),
    )

    ttk.Label(proj, text="Sample profile fits JSON (optional):").grid(
        row=5,
        column=0,
        sticky="w",
        padx=6,
        pady=6,
    )
    self.project_sample_profile_fits_entry = ttk.Entry(
        proj,
        textvariable=self.project_sample_profile_fits_var,
    )
    self.project_sample_profile_fits_entry.grid(
        row=5,
        column=1,
        columnspan=3,
        sticky="ew",
        padx=6,
        pady=6,
    )
    self.project_sample_profile_fits_editor_btn = ttk.Button(
        proj,
        text="Open sample profile fits JSON editor",
        command=self._open_project_sample_profile_fits_editor,
    )
    self.project_sample_profile_fits_editor_btn.grid(
        row=6,
        column=0,
        columnspan=4,
        sticky="ew",
        padx=6,
        pady=(0, 6),
    )

    ttk.Label(proj, text="Locale identity bundles JSON (optional):").grid(
        row=7,
        column=0,
        sticky="w",
        padx=6,
        pady=6,
    )
    self.project_locale_identity_bundles_entry = ttk.Entry(
        proj,
        textvariable=self.project_locale_identity_bundles_var,
    )
    self.project_locale_identity_bundles_entry.grid(
        row=7,
        column=1,
        columnspan=3,
        sticky="ew",
        padx=6,
        pady=6,
    )
    self.project_locale_identity_bundles_editor_btn = ttk.Button(
        proj,
        text="Open locale identity bundles JSON editor",
        command=self._open_project_locale_identity_bundles_editor,
    )
    self.project_locale_identity_bundles_editor_btn.grid(
        row=8,
        column=0,
        columnspan=4,
        sticky="ew",
        padx=6,
        pady=(0, 6),
    )

    btns = ttk.Frame(proj)
    btns.grid(row=9, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))
    btns.columnconfigure(0, weight=1)
    btns.columnconfigure(1, weight=1)

    ttk.Button(btns, text="Save project JSON", command=self._save_project).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    ttk.Button(btns, text="Load project JSON", command=self._load_project).grid(
        row=0, column=1, sticky="ew", padx=(6, 0)
    )

    # Validation Panels
    validation_section = CollapsibleSection(root, title="Schema validation", start_collapsed=False)
    validation_section.pack(fill="x", pady=(10, 0))
    self.validation_section = validation_section

    validation_panel = ttk.LabelFrame(validation_section.content, text="", padding=10)
    validation_panel.pack(fill="x", expand=True)

    top = ttk.Frame(validation_panel)
    top.pack(fill="x")

    ttk.Button(top, text="Run validation", command=self._run_validation).pack(side="left")

    self.validation_summary_var = tk.StringVar(value="No validation run yet.")
    ttk.Label(top, textvariable=self.validation_summary_var).pack(side="left", padx=10)

    self.heatmap = ValidationHeatmap(validation_panel, on_info=self._on_validation_heatmap_info)
    self.heatmap.pack(fill="both", expand=True, pady=(8, 0))
    self.inline_validation = InlineValidationSummary(
        validation_panel,
        on_jump=self._jump_to_validation_issue,
    )
    self.inline_validation.pack(fill="x", pady=(8, 0))


    # =========================
    # Main area: Tables | Table editor | Relationships
    # (pack main on root; grid inside main)
    # =========================
    main = ttk.Frame(root)
    main.pack(fill="both", expand=True, pady=(10, 0))

    main.columnconfigure(0, weight=1)  # tables
    main.columnconfigure(1, weight=3)  # table editor
    main.columnconfigure(2, weight=2)  # relationships
    main.rowconfigure(0, weight=1)

    # ---- Left: tables list (pack inside left)
    left_section = CollapsibleSection(main, title="Tables")
    left_section.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    self.tables_section = left_section
    left = ttk.LabelFrame(left_section.content, text="", padding=10)  # inner panel
    left.pack(fill="both", expand=True)


    self.tables_list = tk.Listbox(left, height=12)
    self.tables_list.pack(fill="both", expand=True)
    self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

    left_btns = ttk.Frame(left)
    left_btns.pack(fill="x", pady=(10, 0))
    ttk.Button(left_btns, text="+ Add table", command=self._add_table).pack(fill="x", pady=4)
    ttk.Button(left_btns, text="Remove selected", command=self._remove_table).pack(fill="x", pady=4)

    # ---- Middle: table editor (pack inside right)
    right_section = CollapsibleSection(main, title="Table editor")
    right_section.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
    self.table_editor_section = right_section
    right = ttk.LabelFrame(right_section.content, text="", padding=10)
    right.pack(fill="both", expand=True)

    # Table properties (grid inside props)
    props = ttk.LabelFrame(right, text="Table properties", padding=10)
    props.pack(fill="x")
    props.columnconfigure(1, weight=1)

    ttk.Label(props, text="Table name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    self.table_name_entry = ttk.Entry(props, textvariable=self.table_name_var)
    self.table_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="Row count (root tables (0 for children enables auto-sizing)):").grid(row=1, column=0, sticky="w", padx=6, pady=6)
    self.row_count_entry = ttk.Entry(props, textvariable=self.row_count_var)
    self.row_count_entry.grid(row=1, column=1, sticky="w", padx=6, pady=6)

    ttk.Label(props, text="Unique business keys (optional):").grid(row=2, column=0, sticky="w", padx=6, pady=6)
    self.table_business_key_unique_count_entry = ttk.Entry(props, textvariable=self.table_business_key_unique_count_var)
    self.table_business_key_unique_count_entry.grid(row=2, column=1, sticky="w", padx=6, pady=6)

    ttk.Label(props, text="Business key columns (comma):").grid(row=3, column=0, sticky="w", padx=6, pady=6)
    self.table_business_key_entry = ttk.Entry(props, textvariable=self.table_business_key_var)
    self.table_business_key_entry.grid(row=3, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="Business key static columns (comma):").grid(row=4, column=0, sticky="w", padx=6, pady=6)
    self.table_business_key_static_entry = ttk.Entry(
        props,
        textvariable=self.table_business_key_static_columns_var,
    )
    self.table_business_key_static_entry.grid(row=4, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="Business key changing columns (comma):").grid(row=5, column=0, sticky="w", padx=6, pady=6)
    self.table_business_key_changing_entry = ttk.Entry(
        props,
        textvariable=self.table_business_key_changing_columns_var,
    )
    self.table_business_key_changing_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="SCD mode:").grid(row=6, column=0, sticky="w", padx=6, pady=6)
    self.table_scd_mode_combo = ttk.Combobox(
        props,
        values=SCD_MODES,
        textvariable=self.table_scd_mode_var,
        state="readonly",
        width=12,
    )
    self.table_scd_mode_combo.grid(row=6, column=1, sticky="w", padx=6, pady=6)

    ttk.Label(props, text="SCD tracked columns (comma):").grid(row=7, column=0, sticky="w", padx=6, pady=6)
    self.table_scd_tracked_entry = ttk.Entry(props, textvariable=self.table_scd_tracked_columns_var)
    self.table_scd_tracked_entry.grid(row=7, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="SCD active from column:").grid(row=8, column=0, sticky="w", padx=6, pady=6)
    self.table_scd_active_from_entry = ttk.Entry(props, textvariable=self.table_scd_active_from_var)
    self.table_scd_active_from_entry.grid(row=8, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="SCD active to column:").grid(row=9, column=0, sticky="w", padx=6, pady=6)
    self.table_scd_active_to_entry = ttk.Entry(props, textvariable=self.table_scd_active_to_var)
    self.table_scd_active_to_entry.grid(row=9, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(props, text="Correlation groups JSON (optional):").grid(row=10, column=0, sticky="w", padx=6, pady=6)
    self.table_correlation_groups_entry = ttk.Entry(props, textvariable=self.table_correlation_groups_var)
    self.table_correlation_groups_entry.grid(row=10, column=1, sticky="ew", padx=6, pady=6)

    self.table_correlation_groups_editor_btn = ttk.Button(
        props,
        text="Open correlation groups JSON editor",
        command=self._open_table_correlation_groups_editor,
    )
    self.table_correlation_groups_editor_btn.grid(row=11, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))

    self.apply_table_btn = ttk.Button(props, text="Apply table changes", command=self._apply_table_changes)
    self.apply_table_btn.grid(row=12, column=0, columnspan=2, sticky="ew", padx=6, pady=(10, 0))

    # Column editor (grid inside col)
    col = ttk.LabelFrame(right, text="Add column", padding=10)
    col.pack(fill="x", pady=(10, 0))
    col.columnconfigure(1, weight=1)

    ttk.Label(col, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    self.col_name_entry = ttk.Entry(col, textvariable=self.col_name_var)
    self.col_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(col, text="Type:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
    self.col_dtype_combo = ttk.Combobox(
        col, values=DTYPES, textvariable=self.col_dtype_var, state="readonly", width=12
    )
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
    self.col_pattern_entry.bind("<FocusOut>", self._on_pattern_entry_focus_out)

    ttk.Label(col, text="Pattern preset:").grid(row=5, column=0, sticky="w", padx=6, pady=6)
    self.col_pattern_preset_combo = ttk.Combobox(
        col,
        values=list(PATTERN_PRESETS.keys()),
        textvariable=self.col_pattern_preset_var,
        state="readonly",
    )
    self.col_pattern_preset_combo.grid(row=5, column=1, columnspan=3, sticky="ew", padx=6, pady=6)
    self.col_pattern_preset_combo.bind("<<ComboboxSelected>>", self._on_pattern_preset_selected)


    ttk.Label(col, text="Generator:").grid(row=6, column=0, sticky="w", padx=6, pady=6)
    self.col_generator_combo = ttk.Combobox(col, values=GENERATORS, textvariable=self.col_generator_var, state="readonly")
    self.col_generator_combo.grid(row=6, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(col, text="Params (JSON):").grid(row=7, column=0, sticky="w", padx=6, pady=6)
    self.col_params_entry = ttk.Entry(col, textvariable=self.col_params_var)
    self.col_params_entry.grid(row=7, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

    self.col_params_template_btn = ttk.Button(
        col,
        text="Fill params template for selected generator",
        command=self._apply_generator_params_template,
    )
    self.col_params_template_btn.grid(row=8, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 6))
    #Adds Column
    self.add_col_btn = ttk.Button(col, text="Add column to selected table", command=self._add_column)
    self.add_col_btn.grid(row=10, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))
    self.edit_col_btn = ttk.Button(
        col,
        text="Apply edits to selected column",
        command=self._apply_selected_column_changes,
    )
    self.edit_col_btn.grid(row=11, column=0, columnspan=4, sticky="ew", padx=6, pady=(6, 0))

    #Correlation stuff
    ttk.Label(col, text="Depends on (comma):").grid(row=9, column=0, sticky="w", padx=6, pady=6)
    self.col_depends_entry = ttk.Entry(col, textvariable=self.col_depends_var)
    self.col_depends_entry.grid(row=9, column=1, columnspan=3, sticky="ew", padx=6, pady=6)


    # Columns table (pack inside cols_frame)
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
    self.columns_tree.bind("<<TreeviewSelect>>", self._on_column_selected)
    install_treeview_keyboard_support(self.columns_tree, include_headers=True)

    yscroll = ttk.Scrollbar(cols_frame, orient="vertical", command=self.columns_tree.yview)
    self.columns_tree.configure(yscrollcommand=yscroll.set)

    self.columns_tree.pack(side="left", fill="both", expand=True)
    yscroll.pack(side="right", fill="y")

    col_actions = ttk.Frame(right)
    col_actions.pack(fill="x", pady=(8, 0))
    ttk.Button(col_actions, text="Remove selected column", command=self._remove_selected_column).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(col_actions, text="Move up", command=lambda: self._move_selected_column(-1)).pack(side="left", padx=6)
    ttk.Button(col_actions, text="Move down", command=lambda: self._move_selected_column(1)).pack(side="left", padx=6)

    # ---- Right: relationships editor (grid/pack inside rel)
    rel_section = CollapsibleSection(main, title="Relationships (FKs)")
    rel_section.grid(row=0, column=2, sticky="nsew")
    self.relationships_section = rel_section
    rel = ttk.LabelFrame(rel_section.content, text="", padding=10)
    rel.pack(fill="both", expand=True)
    rel.columnconfigure(1, weight=1)
    rel.rowconfigure(8, weight=1)

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

    ttk.Label(rel, text="Parent selection JSON (optional):").grid(row=5, column=0, sticky="w", padx=6, pady=6)
    self.fk_parent_selection_entry = ttk.Entry(rel, textvariable=self.fk_parent_selection_var)
    self.fk_parent_selection_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(rel, text="Child count distribution JSON (optional):").grid(row=6, column=0, sticky="w", padx=6, pady=6)
    self.fk_child_count_distribution_entry = ttk.Entry(rel, textvariable=self.fk_child_count_distribution_var)
    self.fk_child_count_distribution_entry.grid(row=6, column=1, sticky="ew", padx=6, pady=6)

    self.add_fk_btn = ttk.Button(rel, text="Add relationship", command=self._add_fk)
    self.add_fk_btn.grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=(10, 8))

    fk_frame = ttk.LabelFrame(rel, text="Defined relationships", padding=8)
    fk_frame.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=6, pady=(6, 0))
    fk_frame.rowconfigure(0, weight=1)
    fk_frame.columnconfigure(0, weight=1)

    fk_cols = ("parent", "parent_pk", "child", "child_fk", "min", "max", "distribution")
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
    self.fks_tree.column("distribution", width=180)
    install_treeview_keyboard_support(self.fks_tree, include_headers=True)

    y2 = ttk.Scrollbar(fk_frame, orient="vertical", command=self.fks_tree.yview)
    self.fks_tree.configure(yscrollcommand=y2.set)

    self.fks_tree.grid(row=0, column=0, sticky="nsew")
    y2.grid(row=0, column=1, sticky="ns")

    self.remove_fk_btn = ttk.Button(rel, text="Remove selected relationship", command=self._remove_selected_fk)
    self.remove_fk_btn.grid(row=9, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 0))

    # =========================
    # Bottom: Generate / Preview / Export / SQLite
    # (pack bottom; grid inside bottom)
    # =========================
    bottom_section = CollapsibleSection(root, title="Generate / Preview / Export / SQLite")
    bottom_section.pack(fill="both", expand=True, pady=(12, 0))

    bottom = ttk.LabelFrame(bottom_section.content, text="", padding=12)
    bottom.pack(fill="both", expand=True)

    bottom.columnconfigure(1, weight=1)
    bottom.rowconfigure(3, weight=1)

    ttk.Label(bottom, text="SQLite DB path:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    ttk.Entry(bottom, textvariable=self.db_path_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
    ttk.Button(bottom, text="Browse…", command=self._browse_db_path).grid(row=0, column=2, padx=6, pady=6)

    ttk.Label(bottom, text="Export format:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
    self.export_option_combo = ttk.Combobox(
        bottom,
        values=EXPORT_OPTIONS,
        textvariable=self.export_option_var,
        state="readonly",
    )
    self.export_option_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

    actions = ttk.Frame(bottom)
    actions.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 10))
    actions.columnconfigure(0, weight=1)
    actions.columnconfigure(1, weight=1)
    actions.columnconfigure(2, weight=1)
    actions.columnconfigure(3, weight=1)

    self.generate_btn = ttk.Button(actions, text="Generate data (all tables)", command=self._on_generate_project)
    self.generate_btn.grid(row=0, column=0, sticky="ew", padx=4)

    self.export_btn = ttk.Button(actions, text="Export data", command=self._on_export_data)
    self.export_btn.grid(row=0, column=1, sticky="ew", padx=4)

    self.sample_btn = ttk.Button(actions, text="Generate sample (10 rows/table)", command=self._on_generate_sample)
    self.sample_btn.grid(row=0, column=2, sticky="ew", padx=4)

    self.clear_btn = ttk.Button(actions, text="Clear generated data", command=self._clear_generated)
    self.clear_btn.grid(row=0, column=3, sticky="ew", padx=4)

    preview_area = ttk.Frame(bottom)
    preview_area.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
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
    ttk.Entry(left_preview, textvariable=self.preview_limit_var, width=10).grid(row=3, column=0, sticky="w", pady=(0, 8))

    self.preview_paging_chk = ttk.Checkbutton(
        left_preview,
        text="Use paged preview",
        variable=self.preview_paging_enabled_var,
        command=self._on_preview_paging_toggled,
    )
    self.preview_paging_chk.grid(row=4, column=0, sticky="w", pady=(0, 6))

    ttk.Label(left_preview, text="Page size:").grid(row=5, column=0, sticky="w")
    self.preview_page_size_combo = ttk.Combobox(
        left_preview,
        textvariable=self.preview_page_size_var,
        values=["50", "100", "200", "500"],
        state="readonly",
        width=8,
    )
    self.preview_page_size_combo.grid(row=6, column=0, sticky="w", pady=(0, 8))
    self.preview_page_size_combo.bind("<<ComboboxSelected>>", self._on_preview_page_size_changed)

    self.preview_btn = ttk.Button(left_preview, text="Refresh preview", command=self._refresh_preview)
    self.preview_btn.grid(row=7, column=0, sticky="ew")

    self.preview_columns_btn = ttk.Button(
        left_preview,
        text="Choose preview columns",
        command=self._open_preview_column_chooser,
    )
    self.preview_columns_btn.grid(row=8, column=0, sticky="ew", pady=(6, 0))

    self.progress = ttk.Progressbar(left_preview, mode="indeterminate")
    self.progress.grid(row=9, column=0, sticky="ew", pady=(14, 0))

    right_preview = ttk.LabelFrame(preview_area, text="Data preview", padding=8)
    right_preview.grid(row=0, column=1, sticky="nsew")
    right_preview.rowconfigure(0, weight=1)
    right_preview.columnconfigure(0, weight=1)

    self.preview_table = TableView(right_preview, height=12)
    self.preview_table.grid(row=0, column=0, sticky="nsew")
    self.preview_table.configure_large_data_mode(
        enabled=True,
        threshold_rows=1000,
        chunk_size=150,
        auto_pagination=False,
        auto_page_size=100,
    )
    self.preview_table.disable_pagination()
    self.preview_tree = self.preview_table.tree

    # Status line (pack on root)
    ttk.Label(root, textvariable=self.status_var).pack(anchor="w", pady=(10, 0))

