from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _starter_fixture_abspath() -> Path:
    # project_io.py lives in src/gui/schema/editor; repo root is parents[4]
    return Path(__file__).resolve().parents[4] / STARTER_FIXTURE_PATH


def _build_starter_project(seed: int) -> SchemaProject:
    customers = TableSpec(
        table_name="customers",
        row_count=120,
        columns=[
            ColumnSpec(name="customer_id", dtype="int", nullable=False, primary_key=True),
            ColumnSpec(name="customer_name", dtype="text", nullable=False),
            ColumnSpec(
                name="segment",
                dtype="text",
                nullable=False,
                generator="choice_weighted",
                params={"choices": ["enterprise", "mid_market", "consumer"], "weights": [0.2, 0.3, 0.5]},
            ),
        ],
    )
    orders = TableSpec(
        table_name="orders",
        row_count=300,
        columns=[
            ColumnSpec(name="order_id", dtype="int", nullable=False, primary_key=True),
            ColumnSpec(name="customer_id", dtype="int", nullable=False),
            ColumnSpec(
                name="order_total",
                dtype="decimal",
                nullable=False,
                generator="money",
                params={"min": 5.0, "max": 750.0, "decimals": 2},
            ),
            ColumnSpec(
                name="ordered_at",
                dtype="datetime",
                nullable=False,
                generator="timestamp_utc",
                params={"start": "2024-01-01T00:00:00Z", "end": "2026-12-31T23:59:59Z"},
            ),
        ],
    )
    return SchemaProject(
        name="starter_project",
        seed=seed,
        tables=[customers, orders],
        foreign_keys=[
            ForeignKeySpec(
                parent_table="customers",
                parent_column="customer_id",
                child_table="orders",
                child_column="customer_id",
                min_children=1,
                max_children=4,
            )
        ],
        timeline_constraints=None,
        data_quality_profiles=None,
        sample_profile_fits=None,
        locale_identity_bundles=None,
    )


def _create_starter_schema(self) -> None:
    if not self._project_io_guard(action="create starter schema"):
        return
    if self.project.tables and not self.confirm_discard_or_save(action_name="creating a starter schema"):
        return

    try:
        starter_seed = int(self.seed_var.get().strip())
    except Exception:
        starter_seed = int(getattr(self.cfg, "seed", 12345))

    try:
        project = self._build_starter_project(starter_seed)
        validate_project(project)
    except Exception as exc:
        self._show_error_dialog(
            "Starter schema",
            f"First-run quick start: could not build starter schema ({exc}). "
            "Fix: create a table manually or load a valid project JSON file.",
        )
        return

    self._apply_loaded_project(project, "starter schema (built-in)")
    self.set_status(
        "Starter schema ready. Next action: open Generate tab and click 'Generate sample (10 rows/table)'."
    )
    self._show_toast("Starter schema created.", level="success")


def _load_starter_fixture_shortcut(self) -> None:
    if not self._project_io_guard(action="load starter fixture"):
        return
    if self.project.tables and not self.confirm_discard_or_save(action_name="loading starter fixture"):
        return

    fixture_path = self._starter_fixture_abspath()
    if not fixture_path.exists():
        self._show_error_dialog(
            "Starter fixture",
            "First-run quick start: starter fixture 'tests/fixtures/default_schema_project.json' was not found. "
            "Fix: restore the fixture file or use 'Create starter schema'.",
        )
        return

    try:
        project = load_project_from_json(str(fixture_path))
    except Exception as exc:
        self._show_error_dialog(
            "Starter fixture",
            f"First-run quick start: failed to load starter fixture ({exc}). "
            "Fix: use 'Create starter schema' or choose a valid project JSON file.",
        )
        return

    self._apply_loaded_project(project, STARTER_FIXTURE_PATH.as_posix())
    self.set_status(
        "Starter fixture loaded. Next action: open Generate tab and click 'Generate sample (10 rows/table)'."
    )
    self._show_toast("Starter fixture loaded.", level="success")


def _start_save_project_async(self) -> bool:
    if not self._project_io_guard(action="save project JSON"):
        return False
    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Save failed", str(exc))
        return False

    path = filedialog.asksaveasfilename(
        title="Save project as JSON",
        defaultextension=".json",
        filetypes=[("JSON", "*.json"), ("All files", "*.*")],
    )
    if not path:
        self.set_status("Save project JSON cancelled.")
        return False

    project_snapshot = self.project
    started = self.project_io_lifecycle.run_async(
        worker=lambda: self._save_project_async_worker(project_snapshot, path),
        on_done=self._on_save_project_async_done,
        on_failed=lambda message: self._on_project_io_failed("Save failed", message),
        phase_label="Saving project JSON...",
        success_phase="Project save complete.",
        failure_phase="Project save failed.",
    )
    return bool(started)


def _save_project_async_worker(project_snapshot, path: str) -> str:
    save_project_to_json(project_snapshot, path)
    return path


def _on_save_project_async_done(self, payload: object) -> None:
    path = str(payload)
    self._mark_saved_baseline()
    self.set_status(f"Saved project: {path}")
    self._show_toast("Project saved.", level="success")


def _start_load_project_async(self) -> None:
    if not self._project_io_guard(action="load project JSON"):
        return
    if not self.confirm_discard_or_save(action_name="loading another project"):
        return

    path = filedialog.askopenfilename(
        title="Load project JSON",
        filetypes=[("JSON", "*.json"), ("All files", "*.*")],
    )
    if not path:
        self.set_status("Load project JSON cancelled.")
        return

    self.project_io_lifecycle.run_async(
        worker=lambda: self._load_project_async_worker(path),
        on_done=self._on_load_project_async_done,
        on_failed=lambda message: self._on_project_io_failed("Load failed", message),
        phase_label="Loading project JSON...",
        success_phase="Project load complete.",
        failure_phase="Project load failed.",
    )


def _load_project_async_worker(path: str) -> tuple[str, object]:
    project = load_project_from_json(path)
    return path, project


def _on_load_project_async_done(self, payload: object) -> None:
    if not isinstance(payload, tuple) or len(payload) != 2:
        self._on_project_io_failed(
            "Load failed",
            "Load project JSON: invalid async payload. "
            "Fix: retry load and capture diagnostics if the issue repeats.",
        )
        return
    path, project = payload
    self._apply_loaded_project(project, str(path))


def _apply_loaded_project(self, project: object, path: str) -> None:
    self._suspend_project_meta_dirty = True
    try:
        self.project = project
        self.project_name_var.set(self.project.name)
        self.seed_var.set(str(self.project.seed))
        self.project_timeline_constraints_var.set(
            json.dumps(self.project.timeline_constraints, sort_keys=True) if self.project.timeline_constraints else ""
        )
        self.project_data_quality_profiles_var.set(
            json.dumps(self.project.data_quality_profiles, sort_keys=True)
            if self.project.data_quality_profiles
            else ""
        )
        self.project_sample_profile_fits_var.set(
            json.dumps(self.project.sample_profile_fits, sort_keys=True)
            if self.project.sample_profile_fits
            else ""
        )
        self.project_locale_identity_bundles_var.set(
            json.dumps(self.project.locale_identity_bundles, sort_keys=True)
            if self.project.locale_identity_bundles
            else ""
        )
    finally:
        self._suspend_project_meta_dirty = False

    self.selected_table_index = None
    self._refresh_tables_list()
    self._refresh_columns_tree()
    self._set_table_editor_enabled(False)
    self._refresh_fk_dropdowns()
    self._refresh_fks_tree()
    self.generated_rows = {}
    if hasattr(self, "preview_table_combo"):
        self.preview_table_combo.configure(values=())
    self.preview_table_var.set("")
    self._preview_column_preferences.clear()
    self._clear_preview_tree()
    self._reset_undo_history()
    self._run_validation_full()
    self.set_status(f"Loaded project: {path}")
    self._show_toast("Project loaded.", level="success")
    self._refresh_onboarding_hints()


def _save_project(self) -> bool:
    before_status = self.status_var.get()
    SchemaProjectDesignerScreen._save_project(self)
    after_status = self.status_var.get()
    saved = after_status != before_status and after_status.startswith("Saved project:")
    if saved:
        self._mark_saved_baseline()
        self._show_toast("Project saved.", level="success")
    return saved


def _load_project(self) -> None:
    if not self.confirm_discard_or_save(action_name="loading another project"):
        return
    before_status = self.status_var.get()
    self._suspend_project_meta_dirty = True
    try:
        SchemaProjectDesignerScreen._load_project(self, confirm_unsaved=False)
    finally:
        self._suspend_project_meta_dirty = False
    after_status = self.status_var.get()
    loaded = after_status != before_status and after_status.startswith("Loaded project:")
    if loaded:
        self._reset_undo_history()
        self.generated_rows = {}
        if hasattr(self, "preview_table_combo"):
            self.preview_table_combo.configure(values=())
        self.preview_table_var.set("")
        self._preview_column_preferences.clear()
        self._refresh_inline_validation_summary()
        self._show_toast("Project loaded.", level="success")
        self._refresh_onboarding_hints()
