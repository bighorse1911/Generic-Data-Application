from __future__ import annotations

def build_relationships_panel(self) -> CollapsiblePanel:
    panel = CollapsiblePanel(self.schema_tab, "Relationships", collapsed=False)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    self.relationships_panel = panel
    panel.body.columnconfigure(0, weight=1)
    panel.body.rowconfigure(4, weight=1)

    self.fk_search = SearchEntry(
        panel.body,
        on_change=self._on_fk_search_change,
        delay_ms=VALIDATION_DEBOUNCE_MS,
    )
    self.fk_search.grid(row=0, column=0, sticky="ew")

    form = ttk.LabelFrame(panel.body, text="Add relationship", padding=8)
    form.grid(row=1, column=0, sticky="ew", pady=(8, 0))
    form.columnconfigure(1, weight=1)

    ttk.Label(form, text="Parent table:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
    self.fk_parent_combo = ttk.Combobox(form, textvariable=self.fk_parent_table_var, state="readonly")
    self.fk_parent_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    self.fk_parent_combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_fk_defaults())

    ttk.Label(form, text="Child table:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
    self.fk_child_combo = ttk.Combobox(form, textvariable=self.fk_child_table_var, state="readonly")
    self.fk_child_combo.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
    self.fk_child_combo.bind("<<ComboboxSelected>>", lambda _event: self._sync_fk_defaults())

    ttk.Label(form, text="Child FK column (int):").grid(row=2, column=0, sticky="w", padx=4, pady=3)
    self.fk_child_col_combo = ttk.Combobox(form, textvariable=self.fk_child_column_var, state="readonly")
    self.fk_child_col_combo.grid(row=2, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(form, text="Min children:").grid(row=3, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=self.fk_min_children_var, width=10).grid(row=3, column=1, sticky="w", padx=4, pady=3)
    ttk.Label(form, text="Max children:").grid(row=4, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=self.fk_max_children_var, width=10).grid(row=4, column=1, sticky="w", padx=4, pady=3)

    self.relationships_mode_medium_group = ttk.Frame(form)
    self.relationships_mode_medium_group.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    self.relationships_mode_medium_group.columnconfigure(1, weight=1)

    ttk.Label(self.relationships_mode_medium_group, text="Parent selection JSON (optional):").grid(
        row=0, column=0, sticky="w", padx=4, pady=3
    )
    self.fk_parent_selection_entry = ttk.Entry(
        self.relationships_mode_medium_group,
        textvariable=self.fk_parent_selection_var,
    )
    self.fk_parent_selection_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

    ttk.Label(self.relationships_mode_medium_group, text="Child count distribution JSON (optional):").grid(
        row=1, column=0, sticky="w", padx=4, pady=3
    )
    self.fk_child_count_distribution_entry = ttk.Entry(
        self.relationships_mode_medium_group,
        textvariable=self.fk_child_count_distribution_var,
    )
    self.fk_child_count_distribution_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=3)

    self.add_fk_btn = ttk.Button(form, text="Add relationship", command=self._add_fk)
    self.add_fk_btn.grid(row=6, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 0))

    tree_box = ttk.LabelFrame(panel.body, text="Defined relationships", padding=8)
    tree_box.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
    tree_box.columnconfigure(0, weight=1)
    tree_box.rowconfigure(0, weight=1)

    cols = ("parent", "parent_pk", "child", "child_fk", "min", "max", "distribution")
    self.fks_tree = ttk.Treeview(tree_box, columns=cols, show="headings", height=10)
    for col_name in cols:
        self.fks_tree.heading(col_name, text=col_name)
        self.fks_tree.column(col_name, width=110, anchor="w", stretch=True)
    self.fks_tree.column("distribution", width=180)
    self.fks_tree.grid(row=0, column=0, sticky="nsew")
    self.fks_tree.bind("<<TreeviewSelect>>", self._on_fk_selection_changed)
    yscroll = ttk.Scrollbar(tree_box, orient="vertical", command=self.fks_tree.yview)
    yscroll.grid(row=0, column=1, sticky="ns")
    self.fks_tree.configure(yscrollcommand=yscroll.set)

    paging = ttk.Frame(panel.body)
    paging.grid(row=3, column=0, sticky="ew", pady=(6, 0))
    self.fks_page_var = tk.StringVar(value="No matching relationships.")
    ttk.Label(paging, textvariable=self.fks_page_var).pack(side="left")
    self.fks_prev_btn = ttk.Button(paging, text="Prev", command=self._on_fk_filter_prev_page)
    self.fks_prev_btn.pack(side="right")
    self.fks_next_btn = ttk.Button(paging, text="Next", command=self._on_fk_filter_next_page)
    self.fks_next_btn.pack(side="right", padx=(0, 6))

    self.remove_fk_btn = ttk.Button(panel.body, text="Remove selected relationship", command=self._remove_selected_fk)
    self.remove_fk_btn.grid(row=4, column=0, sticky="ew", pady=(6, 0))
    return panel


