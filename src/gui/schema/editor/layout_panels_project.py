from __future__ import annotations

def build_project_panel(self) -> CollapsiblePanel:
    panel = CollapsiblePanel(self.schema_tab, "Project", collapsed=False)
    panel.pack(fill="x", pady=(0, 10))
    self.project_panel = panel

    panel.body.columnconfigure(0, weight=1)

    settings = ttk.LabelFrame(panel.body, text="Project settings", padding=10)
    settings.grid(row=0, column=0, sticky="ew")
    settings.columnconfigure(1, weight=1)
    settings.columnconfigure(3, weight=1)

    ttk.Label(settings, text="Project name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    ttk.Entry(settings, textvariable=self.project_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

    ttk.Label(settings, text="Seed:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
    ttk.Entry(settings, textvariable=self.seed_var, width=14).grid(row=0, column=3, sticky="w", padx=6, pady=6)

    self.project_complex_group = ttk.Frame(settings)
    self.project_complex_group.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
    self.project_complex_group.columnconfigure(1, weight=1)

    row = 0
    ttk.Label(self.project_complex_group, text="Timeline constraints JSON (optional):").grid(
        row=row, column=0, sticky="w", padx=6, pady=4
    )
    self.project_timeline_constraints_entry = ttk.Entry(
        self.project_complex_group,
        textvariable=self.project_timeline_constraints_var,
    )
    self.project_timeline_constraints_entry.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
    self.project_timeline_constraints_editor_btn = ttk.Button(
        self.project_complex_group,
        text="Open timeline constraints JSON editor",
        command=self._open_project_timeline_constraints_editor,
    )
    self.project_timeline_constraints_editor_btn.grid(row=row, column=2, sticky="ew", padx=6, pady=4)

    row += 1
    ttk.Label(self.project_complex_group, text="Data quality profiles JSON (optional):").grid(
        row=row, column=0, sticky="w", padx=6, pady=4
    )
    self.project_data_quality_profiles_entry = ttk.Entry(
        self.project_complex_group,
        textvariable=self.project_data_quality_profiles_var,
    )
    self.project_data_quality_profiles_entry.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
    self.project_data_quality_profiles_editor_btn = ttk.Button(
        self.project_complex_group,
        text="Open data quality profiles JSON editor",
        command=self._open_project_data_quality_profiles_editor,
    )
    self.project_data_quality_profiles_editor_btn.grid(row=row, column=2, sticky="ew", padx=6, pady=4)

    row += 1
    ttk.Label(self.project_complex_group, text="Sample profile fits JSON (optional):").grid(
        row=row, column=0, sticky="w", padx=6, pady=4
    )
    self.project_sample_profile_fits_entry = ttk.Entry(
        self.project_complex_group,
        textvariable=self.project_sample_profile_fits_var,
    )
    self.project_sample_profile_fits_entry.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
    self.project_sample_profile_fits_editor_btn = ttk.Button(
        self.project_complex_group,
        text="Open sample profile fits JSON editor",
        command=self._open_project_sample_profile_fits_editor,
    )
    self.project_sample_profile_fits_editor_btn.grid(row=row, column=2, sticky="ew", padx=6, pady=4)

    row += 1
    ttk.Label(self.project_complex_group, text="Locale identity bundles JSON (optional):").grid(
        row=row, column=0, sticky="w", padx=6, pady=4
    )
    self.project_locale_identity_bundles_entry = ttk.Entry(
        self.project_complex_group,
        textvariable=self.project_locale_identity_bundles_var,
    )
    self.project_locale_identity_bundles_entry.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
    self.project_locale_identity_bundles_editor_btn = ttk.Button(
        self.project_complex_group,
        text="Open locale identity bundles JSON editor",
        command=self._open_project_locale_identity_bundles_editor,
    )
    self.project_locale_identity_bundles_editor_btn.grid(row=row, column=2, sticky="ew", padx=6, pady=4)

    actions = ttk.Frame(panel.body)
    actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    for col in range(7):
        actions.columnconfigure(col, weight=1)

    self.save_project_btn = ttk.Button(actions, text="Save project JSON", command=self._save_project)
    self.save_project_btn.grid(row=0, column=0, sticky="ew", padx=4)
    self.load_project_btn = ttk.Button(actions, text="Load project JSON", command=self._load_project)
    self.load_project_btn.grid(row=0, column=1, sticky="ew", padx=4)
    self.create_starter_schema_btn = ttk.Button(
        actions,
        text="Create starter schema",
        command=self._create_starter_schema,
    )
    self.create_starter_schema_btn.grid(row=0, column=2, sticky="ew", padx=4)
    self.load_starter_fixture_btn = ttk.Button(
        actions,
        text="Load starter fixture",
        command=self._load_starter_fixture_shortcut,
    )
    self.load_starter_fixture_btn.grid(row=0, column=3, sticky="ew", padx=4)
    self.run_validation_btn = ttk.Button(actions, text="Run validation", command=self._run_validation_full)
    self.run_validation_btn.grid(row=0, column=4, sticky="ew", padx=4)
    self.undo_btn = ttk.Button(actions, text="Undo", command=self._undo_last_change)
    self.undo_btn.grid(row=0, column=5, sticky="ew", padx=4)
    self.redo_btn = ttk.Button(actions, text="Redo", command=self._redo_last_change)
    self.redo_btn.grid(row=0, column=6, sticky="ew", padx=4)

    self.onboarding_project_hint_var = tk.StringVar(
        value="No schema tables yet. Start with 'Create starter schema' or add your first table."
    )
    ttk.Label(
        panel.body,
        textvariable=self.onboarding_project_hint_var,
        wraplength=980,
        justify="left",
    ).grid(row=2, column=0, sticky="ew", pady=(8, 0))

    validation_panel = ttk.LabelFrame(panel.body, text="Schema validation", padding=10)
    validation_panel.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
    validation_panel.columnconfigure(0, weight=1)
    validation_panel.rowconfigure(1, weight=1)

    top = ttk.Frame(validation_panel)
    top.grid(row=0, column=0, sticky="ew")
    top.columnconfigure(1, weight=1)
    ttk.Label(top, textvariable=self.validation_summary_var).grid(row=0, column=1, sticky="w", padx=(10, 0))

    self.heatmap = ValidationHeatmap(validation_panel, on_info=self._on_validation_heatmap_info)
    self.heatmap.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
    self.inline_validation = InlineValidationSummary(
        validation_panel,
        on_jump=self._jump_to_validation_issue,
    )
    self.inline_validation.grid(row=2, column=0, sticky="ew", pady=(8, 0))
    return panel


