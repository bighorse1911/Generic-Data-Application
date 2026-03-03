from __future__ import annotations

def build_tables_panel(self) -> CollapsiblePanel:
    panel = CollapsiblePanel(self.schema_tab, "Tables", collapsed=False)
    panel.pack(fill="both", expand=True, pady=(0, 10))
    self.tables_panel = panel
    panel.body.columnconfigure(0, weight=1)
    panel.body.rowconfigure(1, weight=1)

    self.tables_search = SearchEntry(
        panel.body,
        on_change=self._on_tables_search_change,
        delay_ms=VALIDATION_DEBOUNCE_MS,
    )
    self.tables_search.grid(row=0, column=0, sticky="ew")

    self.tables_list = tk.Listbox(panel.body, height=10)
    self.tables_list.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
    self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

    actions = ttk.Frame(panel.body)
    actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    actions.columnconfigure(0, weight=1)
    actions.columnconfigure(1, weight=1)
    ttk.Button(actions, text="+ Add table", command=self._add_table).grid(row=0, column=0, sticky="ew", padx=(0, 4))
    ttk.Button(actions, text="Remove selected", command=self._remove_table).grid(row=0, column=1, sticky="ew", padx=(4, 0))
    return panel


