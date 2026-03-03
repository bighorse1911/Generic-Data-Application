from __future__ import annotations


def __init__(self, parent: tk.Widget, app: "object", cfg: AppConfig) -> None:
    if isinstance(self, BaseScreen):
        BaseScreen.__init__(self, parent)
    else:
        ttk.Frame.__init__(self, parent)
    self.app = app
    self.cfg = cfg

    #Scrollable container logic
    self.scroll = ScrollableFrame(self, padding=16)
    self.scroll.pack(fill="both", expand=True)



    # In-memory project
    self.project = SchemaProject(
        name="my_project",
        seed=cfg.seed,
        tables=[],
        foreign_keys=[],
        timeline_constraints=None,
        data_quality_profiles=None,
        sample_profile_fits=None,
        locale_identity_bundles=None,
    )

    # Selection state
    self.selected_table_index: int | None = None

    # Project-level vars
    self.project_name_var = tk.StringVar(value=self.project.name)
    self.seed_var = tk.StringVar(value=str(self.project.seed))
    self.project_timeline_constraints_var = tk.StringVar(
        value=json.dumps(self.project.timeline_constraints, sort_keys=True) if self.project.timeline_constraints else ""
    )
    self.project_data_quality_profiles_var = tk.StringVar(
        value=(
            json.dumps(self.project.data_quality_profiles, sort_keys=True)
            if self.project.data_quality_profiles
            else ""
        )
    )
    self.project_sample_profile_fits_var = tk.StringVar(
        value=(
            json.dumps(self.project.sample_profile_fits, sort_keys=True)
            if self.project.sample_profile_fits
            else ""
        )
    )
    self.project_locale_identity_bundles_var = tk.StringVar(
        value=(
            json.dumps(self.project.locale_identity_bundles, sort_keys=True)
            if self.project.locale_identity_bundles
            else ""
        )
    )
    self.status_var = tk.StringVar(value="Ready.")
    self.error_surface = ErrorSurface(
        context=self.ERROR_SURFACE_CONTEXT,
        dialog_title=self.ERROR_DIALOG_TITLE,
        warning_title=self.WARNING_DIALOG_TITLE,
        show_dialog=show_error_dialog,
        show_warning=show_warning_dialog,
        set_status=self.status_var.set,
    )
    self.toast_center = ToastCenter(self)

    # Table editor vars
    self.table_name_var = tk.StringVar(value="")
    self.row_count_var = tk.StringVar(value="100")
    self.table_business_key_unique_count_var = tk.StringVar(value="")
    self.table_business_key_var = tk.StringVar(value="")
    self.table_business_key_static_columns_var = tk.StringVar(value="")
    self.table_business_key_changing_columns_var = tk.StringVar(value="")
    self.table_scd_mode_var = tk.StringVar(value="")
    self.table_scd_tracked_columns_var = tk.StringVar(value="")
    self.table_scd_active_from_var = tk.StringVar(value="")
    self.table_scd_active_to_var = tk.StringVar(value="")
    self.table_correlation_groups_var = tk.StringVar(value="")

    # Column form vars
    self.col_name_var = tk.StringVar(value="")
    self.col_dtype_var = tk.StringVar(value="text")
    self.col_nullable_var = tk.BooleanVar(value=True)
    self.col_pk_var = tk.BooleanVar(value=False)
    self.col_unique_var = tk.BooleanVar(value=False)
    self.col_min_var = tk.StringVar(value="")
    self.col_max_var = tk.StringVar(value="")
    self.col_choices_var = tk.StringVar(value="")
    self.col_pattern_var = tk.StringVar(value="")
    self.col_pattern_preset_var = tk.StringVar(value=PATTERN_PRESET_CUSTOM)

    #Updated data generation variables
    self.col_generator_var = tk.StringVar(value="")
    self.col_params_var = tk.StringVar(value="")  # JSON text

    self.col_depends_var = tk.StringVar(value="")


    # Relationship editor vars
    self.fk_parent_table_var = tk.StringVar(value="")
    self.fk_child_table_var = tk.StringVar(value="")
    self.fk_child_column_var = tk.StringVar(value="")
    self.fk_min_children_var = tk.StringVar(value="1")
    self.fk_max_children_var = tk.StringVar(value="3")
    self.fk_parent_selection_var = tk.StringVar(value="")
    self.fk_child_count_distribution_var = tk.StringVar(value="")

    #Validation
    self.validation_summary_var = tk.StringVar(value="No validation run yet.")


    # Generation/preview state
    self.is_running = False
    self.generated_rows: dict[str, list[dict[str, object]]] = {}

    # Output / DB vars
    self.db_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "schema_project.db"))
    self.export_option_var = tk.StringVar(value=EXPORT_OPTION_CSV)
    self.preview_table_var = tk.StringVar(value="")
    self.preview_paging_enabled_var = tk.BooleanVar(value=False)
    self.preview_page_size_var = tk.StringVar(value="100")

    #Validation state variables
    self.last_validation_errors = 0
    self.last_validation_warnings = 0
    self._preview_source_table = ""
    self._preview_source_rows: list[dict[str, object]] = []
    self._preview_column_preferences: dict[str, list[str]] = {}
    self._dirty = False
    self._dirty_indicator_var = tk.StringVar(value="")
    self._suspend_dirty_tracking = False


    self._build()
    self.col_dtype_var.trace_add("write", self._on_column_dtype_changed)
    self.col_generator_var.trace_add("write", self._on_column_generator_changed)
    self.project_name_var.trace_add("write", self._on_project_meta_changed)
    self.seed_var.trace_add("write", self._on_project_meta_changed)
    self.project_timeline_constraints_var.trace_add("write", self._on_project_meta_changed)
    self.project_data_quality_profiles_var.trace_add("write", self._on_project_meta_changed)
    self.project_sample_profile_fits_var.trace_add("write", self._on_project_meta_changed)
    self.project_locale_identity_bundles_var.trace_add("write", self._on_project_meta_changed)
    self._refresh_generator_options_for_dtype()
    self._sync_pattern_preset_from_pattern()
    self._refresh_tables_list()
    self._set_table_editor_enabled(False)
    self._refresh_fk_dropdowns()
    self._refresh_fks_tree()
    self._on_preview_paging_toggled()
    self._mark_clean()

    #Final validation
    self._run_validation()

