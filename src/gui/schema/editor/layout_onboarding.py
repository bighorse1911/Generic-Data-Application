from __future__ import annotations


def _refresh_onboarding_hints(self) -> None:
    has_tables = bool(self.project.tables)
    has_generated = bool(self.generated_rows)
    preview_table = self.preview_table_var.get().strip()
    preview_ready = has_generated and preview_table != "" and preview_table in self.generated_rows

    if hasattr(self, "onboarding_project_hint_var"):
        if not has_tables:
            self.onboarding_project_hint_var.set(
                "No schema tables yet. Start with 'Create starter schema' or add your first table."
            )
        elif len(self.project.tables) < 2:
            self.onboarding_project_hint_var.set(
                "Schema ready. Next action: add another table and define a relationship."
            )
        else:
            self.onboarding_project_hint_var.set(
                "Schema ready. Next action: run validation, then open Generate."
            )

    if hasattr(self, "generate_empty_hint_var"):
        if not has_tables:
            self.generate_empty_hint_var.set(
                "No schema is available for generation yet. Create or load a schema project first."
            )
        elif not has_generated:
            self.generate_empty_hint_var.set(
                "No schema preview data yet. Run 'Generate sample (10 rows/table)' to inspect output."
            )
        elif preview_ready:
            self.generate_empty_hint_var.set(
                "Preview is ready. Adjust columns/page size, then export CSV or SQLite."
            )
        else:
            self.generate_empty_hint_var.set(
                "Generated rows are available. Select a preview table to inspect output."
            )

    project_io_busy = False
    if hasattr(self, "_project_io_running") and hasattr(self, "project_io_lifecycle"):
        try:
            project_io_busy = bool(self._project_io_busy())
        except Exception:
            project_io_busy = False
    busy = bool(self.is_running or project_io_busy)
    starter_state = tk.DISABLED if busy else tk.NORMAL
    for widget_name in ("create_starter_schema_btn", "load_starter_fixture_btn"):
        widget = getattr(self, widget_name, None)
        if widget is not None:
            widget.configure(state=starter_state)
