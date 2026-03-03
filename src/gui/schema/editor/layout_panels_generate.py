from __future__ import annotations

def build_generate_panel(self) -> CollapsiblePanel:
    panel = CollapsiblePanel(self.generate_tab, "Generate / Preview / Export / SQLite", collapsed=False)
    panel.pack(fill="both", expand=True)
    self.generate_panel = panel
    panel.body.columnconfigure(1, weight=1)
    panel.body.rowconfigure(4, weight=1)

    ttk.Label(panel.body, text="SQLite DB path:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    ttk.Entry(panel.body, textvariable=self.db_path_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
    ttk.Button(panel.body, text="Browse...", command=self._browse_db_path).grid(row=0, column=2, padx=6, pady=6)

    ttk.Label(panel.body, text="Export format:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
    self.export_option_combo = ttk.Combobox(
        panel.body,
        values=EXPORT_OPTIONS,
        textvariable=self.export_option_var,
        state="readonly",
    )
    self.export_option_combo.grid(row=1, column=1, sticky="w", padx=6, pady=6)

    actions = ttk.Frame(panel.body)
    actions.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(4, 8))
    for col in range(4):
        actions.columnconfigure(col, weight=1)

    self.generate_btn = ttk.Button(actions, text="Generate data (all tables)", command=self._on_generate_project)
    self.generate_btn.grid(row=0, column=0, sticky="ew", padx=4)
    self.export_btn = ttk.Button(actions, text="Export data", command=self._on_export_data)
    self.export_btn.grid(row=0, column=1, sticky="ew", padx=4)
    self.sample_btn = ttk.Button(actions, text="Generate sample (10 rows/table)", command=self._on_generate_sample)
    self.sample_btn.grid(row=0, column=2, sticky="ew", padx=4)
    self.clear_btn = ttk.Button(actions, text="Clear generated data", command=self._clear_generated)
    self.clear_btn.grid(row=0, column=3, sticky="ew", padx=4)

    self.generate_empty_hint_var = tk.StringVar(
        value="No schema is available for generation yet. Create or load a schema project first."
    )
    ttk.Label(
        panel.body,
        textvariable=self.generate_empty_hint_var,
        wraplength=980,
        justify="left",
    ).grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 8))

    preview_area = ttk.Frame(panel.body)
    preview_area.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
    preview_area.columnconfigure(1, weight=1)
    preview_area.rowconfigure(0, weight=1)

    left = ttk.LabelFrame(preview_area, text="Preview controls", padding=10)
    left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
    left.columnconfigure(0, weight=1)

    ttk.Label(left, text="Table:").grid(row=0, column=0, sticky="w")
    self.preview_table_combo = ttk.Combobox(left, textvariable=self.preview_table_var, state="readonly")
    self.preview_table_combo.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    self.preview_table_combo.bind("<<ComboboxSelected>>", self._on_preview_table_selected)

    ttk.Label(left, text="Max rows to show:").grid(row=2, column=0, sticky="w")
    self.preview_limit_var = tk.StringVar(value="200")
    ttk.Entry(left, textvariable=self.preview_limit_var, width=10).grid(row=3, column=0, sticky="w", pady=(0, 8))

    self.preview_paging_chk = ttk.Checkbutton(
        left,
        text="Use paged preview",
        variable=self.preview_paging_enabled_var,
        command=self._on_preview_paging_toggled,
    )
    self.preview_paging_chk.grid(row=4, column=0, sticky="w", pady=(0, 6))

    ttk.Label(left, text="Page size:").grid(row=5, column=0, sticky="w")
    self.preview_page_size_combo = ttk.Combobox(
        left,
        textvariable=self.preview_page_size_var,
        values=["50", "100", "200", "500"],
        state="readonly",
        width=8,
    )
    self.preview_page_size_combo.grid(row=6, column=0, sticky="w", pady=(0, 8))
    self.preview_page_size_combo.bind("<<ComboboxSelected>>", self._on_preview_page_size_changed)

    self.preview_btn = ttk.Button(left, text="Refresh preview", command=self._refresh_preview)
    self.preview_btn.grid(row=7, column=0, sticky="ew")
    self.preview_columns_btn = ttk.Button(left, text="Choose preview columns", command=self._open_preview_column_chooser)
    self.preview_columns_btn.grid(row=8, column=0, sticky="ew", pady=(6, 0))

    self.progress = ttk.Progressbar(left, mode="indeterminate")
    self.progress.grid(row=9, column=0, sticky="ew", pady=(12, 0))

    right = ttk.LabelFrame(preview_area, text="Data preview", padding=8)
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(0, weight=1)

    self.preview_table = TableView(right, height=12)
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
    return panel




