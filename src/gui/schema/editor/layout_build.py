from __future__ import annotations


def _build(self) -> None:
    if hasattr(self, "scroll"):
        self.scroll.destroy()
    if hasattr(self, "_header_host") and isinstance(self._header_host, tk.Widget):
        self._header_host.destroy()

    self._header_host = ttk.Frame(self)
    self._header_host.pack(fill="x")

    self.scroll = ScrollFrame(self, padding=16)
    self.scroll.pack(fill="both", expand=True)
    self._root_content = self.scroll.content
    self.toast_center = ToastCenter(self)
    self.shortcut_manager = ShortcutManager(self)
    self.focus_controller = FocusController(self)
    self._preview_source_table = ""
    self._preview_source_rows: list[dict[str, object]] = []
    self._preview_column_preferences: dict[str, list[str]] = {}
    self._columns_filter_index: list[IndexedFilterRow] = []
    self._columns_filter_rows: list[IndexedFilterRow] = []
    self._columns_filter_page_index = 0
    self._fk_filter_index: list[IndexedFilterRow] = []
    self._fk_filter_rows: list[IndexedFilterRow] = []
    self._fk_filter_page_index = 0
    self._schema_design_mode_suspended = True
    self._schema_design_mode_trace_name: str | None = None
    self._schema_design_mode_last_applied: SchemaDesignMode = DEFAULT_SCHEMA_DESIGN_MODE
    self._last_out_of_mode_generator_notice: tuple[SchemaDesignMode, str] | None = None
    self.schema_design_mode_var = tk.StringVar(value=DEFAULT_SCHEMA_DESIGN_MODE)

    self.build_header()

    self.main_tabs = Tabs(self._root_content)
    self.main_tabs.pack(fill="both", expand=True)

    self.schema_tab = self.main_tabs.add_tab("Schema")
    self.generate_tab = self.main_tabs.add_tab("Generate")

    self.build_project_panel()
    self.build_tables_panel()
    self.build_columns_panel()
    self.build_relationships_panel()
    self.build_generate_panel()
    self.build_status_bar()
    self.main_tabs.bind("<<NotebookTabChanged>>", self._on_main_tab_changed, add="+")
    self._restore_workspace_state()
    self._apply_schema_design_mode_ui(emit_feedback=False, persist=False)
    if self._schema_design_mode_trace_name is None:
        self._schema_design_mode_trace_name = self.schema_design_mode_var.trace_add(
            "write",
            self._on_schema_design_mode_changed,
        )
    self._schema_design_mode_suspended = False
    self._register_focus_anchors()
    self._register_shortcuts()
    self._suspend_project_meta_dirty = False
    self.project_name_var.trace_add("write", self._on_project_meta_changed)
    self.seed_var.trace_add("write", self._on_project_meta_changed)
    self.project_timeline_constraints_var.trace_add("write", self._on_project_meta_changed)
    self.project_data_quality_profiles_var.trace_add("write", self._on_project_meta_changed)
    self.project_sample_profile_fits_var.trace_add("write", self._on_project_meta_changed)
    self.project_locale_identity_bundles_var.trace_add("write", self._on_project_meta_changed)
    self.enable_dirty_state_guard(context="Schema Project Designer", on_save=self._save_project)
    self.mark_clean()
    self.job_lifecycle = JobLifecycleController(
        set_running=self._set_running,
        run_async=self._run_job_async,
    )
    self.project_io_lifecycle = JobLifecycleController(
        set_running=self._set_project_io_running,
        run_async=self._run_job_async,
    )
    self._project_io_running = False
    self.undo_stack = UndoStack(limit=UNDO_STACK_LIMIT)
    self._undo_saved_project: SchemaProject = self.project
    self._validation_cache_project_issues: list[ValidationIssue] = []
    self._validation_cache_table_issues: dict[str, list[ValidationIssue]] = {}
    self._validation_pending_mode: str = "full"
    self._validation_pending_tables: set[str] = set()
    self._validation_debounce_after_id: str | None = None
    self.bind("<Destroy>", self._on_screen_destroy, add="+")
    self._update_undo_redo_controls()
    self._refresh_onboarding_hints()

    # Keep default platform theme; dark mode is intentionally disabled.
    self.kit_dark_mode_enabled = False


def on_show(self) -> None:
    if hasattr(self, "shortcut_manager"):
        self.shortcut_manager.activate()
    if hasattr(self, "focus_controller"):
        self.focus_controller.focus_default()
    self._refresh_onboarding_hints()


def on_hide(self) -> None:
    self._persist_workspace_state()
    if hasattr(self, "shortcut_manager"):
        self.shortcut_manager.deactivate()


def build_header(self) -> ttk.Frame:
    header_parent = self._header_host if hasattr(self, "_header_host") else self._root_content
    header = BaseScreen.build_header(
        self,
        header_parent,
        title="Schema Project Designer (Kit Preview)",
        back_command=self._on_back_requested,
    )
    ttk.Button(header, text="Notifications", command=self._show_notifications_history).pack(side="right", padx=(0, 6))
    ttk.Button(header, text="Shortcuts", command=self._show_shortcuts_help).pack(side="right")
    return header


def build_status_bar(self) -> ttk.Frame:
    return BaseScreen.build_status_bar(self, self._root_content, include_progress=False)
