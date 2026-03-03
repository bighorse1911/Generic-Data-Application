from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _on_generate_project(self) -> None:
    if self._project_io_busy():
        self.set_status(
            "Cannot generate: a project save/load operation is currently running. "
            "Fix: wait for project save/load to finish."
        )
        return
    if self.is_running:
        return
    self._run_validation_full()
    if self.last_validation_errors > 0:
        self._show_error_dialog(
            "Cannot generate",
            "Generate action: schema has validation errors. "
            "Fix: run validation and resolve all error cells first.",
        )
        return
    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Invalid project", str(exc))
        return

    self.job_lifecycle.run_async(
        worker=lambda: generate_project_rows(self.project),
        on_done=self._on_generated_ok,
        on_failed=self._on_job_failed,
        phase_label="Generating data for all tables...",
    )


def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
    SchemaProjectDesignerScreen._on_generated_ok(self, rows)
    self._refresh_onboarding_hints()


def _clear_generated(self) -> None:
    SchemaProjectDesignerScreen._clear_generated(self)
    self._refresh_onboarding_hints()


def _on_export_csv(self) -> None:
    if self._project_io_busy():
        self.set_status(
            "Cannot export CSV: a project save/load operation is currently running. "
            "Fix: wait for project save/load to finish."
        )
        return
    if self.is_running:
        return
    if not self.generated_rows:
        SchemaProjectDesignerScreen._on_export_csv(self)
        return

    self._run_validation_full()
    if self.last_validation_errors > 0:
        self._show_error_dialog(
            "Cannot export",
            "CSV export action: schema has validation errors. "
            "Fix: run validation and resolve all error cells first.",
        )
        return
    SchemaProjectDesignerScreen._on_export_csv(self)


def _on_create_insert_sqlite(self) -> None:
    if self._project_io_busy():
        self.set_status(
            "Cannot run SQLite export: a project save/load operation is currently running. "
            "Fix: wait for project save/load to finish."
        )
        return
    if self.is_running:
        return
    self._run_validation_full()
    if self.last_validation_errors > 0:
        self._show_error_dialog(
            "Cannot export",
            "SQLite export action: schema has validation errors. "
            "Fix: run validation and resolve all error cells first.",
        )
        return
    if not self.generated_rows:
        self._show_warning_dialog("No data", "Generate data first.")
        return

    db_path = self.db_path_var.get().strip()
    if not db_path:
        self._show_error_dialog(
            "Missing DB path",
            "Generate / Preview / Export / SQLite panel: SQLite DB path is required. "
            "Fix: choose a SQLite database file path.",
        )
        return

    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Invalid project", str(exc))
        return

    def _sqlite_job() -> dict[str, int]:
        create_tables(db_path, self.project)
        return insert_project_rows(db_path, self.project, self.generated_rows, chunk_size=5000)

    self.job_lifecycle.run_async(
        worker=_sqlite_job,
        on_done=lambda counts: self._on_sqlite_ok(db_path, counts),
        on_failed=self._on_job_failed,
        phase_label="Creating tables and inserting rows into SQLite...",
    )


def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
    SchemaProjectDesignerScreen._on_sqlite_ok(self, db_path, counts)


def _on_generate_sample(self) -> None:
    if self._project_io_busy():
        self.set_status(
            "Cannot generate sample: a project save/load operation is currently running. "
            "Fix: wait for project save/load to finish."
        )
        return
    if self.is_running:
        return

    self._run_validation_full()
    if self.last_validation_errors > 0:
        self._show_error_dialog(
            "Cannot generate",
            "Generate sample action: schema has validation errors. "
            "Fix: run validation and resolve all error cells first.",
        )
        return

    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Invalid project", str(exc))
        return

    sample_project = self._make_sample_project(10)
    self.job_lifecycle.run_async(
        worker=lambda: generate_project_rows(sample_project),
        on_done=self._on_generated_ok,
        on_failed=self._on_job_failed,
        phase_label="Generating sample data (10 rows per root table)...",
    )
