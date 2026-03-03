from __future__ import annotations



def _on_generate_project(self) -> None:
    if self.is_running:
        return
    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Invalid project", str(exc))
        return

    self._set_running(True, "Generating data for all tables…")

    def work():
        try:
            rows = generate_project_rows(self.project)
            self._post_ui_callback(lambda: self._on_generated_ok(rows))
        except Exception as exc:
            logger.exception("Generation failed: %s", exc)
            msg = str(exc)
            self._post_ui_callback(lambda m=msg: self._on_job_failed(m))

    threading.Thread(target=work, daemon=True).start()

def _set_running(self, running: bool, msg: str) -> None:
    self.is_running = running
    self.status_var.set(msg)
    if running:
        self.progress.start(10)
    else:
        self.progress.stop()

    # disable buttons while running
    state = tk.DISABLED if running else tk.NORMAL
    self.generate_btn.configure(state=state)
    self.export_btn.configure(state=state)
    self.export_option_combo.configure(state=("disabled" if running else "readonly"))
    self.clear_btn.configure(state=state)
    self.preview_btn.configure(state=state)
    if hasattr(self, "preview_columns_btn"):
        self.preview_columns_btn.configure(state=state)
    if hasattr(self, "preview_paging_chk"):
        self.preview_paging_chk.configure(state=state)
    if hasattr(self, "preview_page_size_combo"):
        if running:
            self.preview_page_size_combo.configure(state=tk.DISABLED)
        else:
            paging_enabled_var = getattr(self, "preview_paging_enabled_var", None)
            paging_enabled = bool(paging_enabled_var.get()) if paging_enabled_var is not None else False
            self.preview_page_size_combo.configure(
                state=("readonly" if paging_enabled else tk.DISABLED)
            )

def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
    self.generated_rows = rows
    self._set_running(False, "Generation complete.")

    # update preview table dropdown
    table_names = list(rows.keys())
    self.preview_table_combo["values"] = table_names
    if table_names:
        if not self.preview_table_var.get() or self.preview_table_var.get() not in table_names:
            self.preview_table_var.set(table_names[0])
        self._refresh_preview()

    # quick summary
    summary = ", ".join([f"{t}={len(r)}" for t, r in rows.items()])
    total_rows = sum(len(v) for v in rows.values())
    self._notify(
        f"Generated {total_rows} rows across {len(rows)} tables ({summary}).",
        level="success",
        duration_ms=4200,
    )

def _on_export_data(self) -> None:
    if self.is_running:
        return

    try:
        export_option = validate_export_option(self.export_option_var.get())
    except ValueError as exc:
        self._show_error_dialog("Invalid export option", str(exc))
        return

    if export_option == EXPORT_OPTION_CSV:
        self._on_export_csv()
        return
    if export_option == EXPORT_OPTION_SQLITE:
        self._on_create_insert_sqlite()
        return

    # Defensive fallback: export options are validated above.
    self._show_error_dialog(
        "Invalid export option",
        _gui_error(
            "Generate / Preview / Export / SQLite panel",
            f"unsupported export option '{export_option}'",
            "choose one of the supported export options",
        ),
    )

def _on_export_csv(self) -> None:
    if self.is_running:
        return
    if not self.generated_rows:
        self._show_warning_dialog("Nothing to export", "Generate data first.")
        return

    folder = filedialog.askdirectory(title="Choose a folder to export CSVs into")
    if not folder:
        return

    try:
        for table, rows in self.generated_rows.items():
            if not rows:
                continue
            path = os.path.join(folder, f"{table}.csv")
            cols = list(rows[0].keys())

            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow([_csv_export_value(r.get(c)) for c in cols])

        self._notify(
            f"Exported one CSV per table to '{folder}'.",
            level="success",
            duration_ms=4200,
        )
    except Exception as exc:
        self._show_error_dialog("Export failed", str(exc))

def _on_create_insert_sqlite(self) -> None:
    if self.is_running:
        return
    if not self.generated_rows:
        self._show_warning_dialog("No data", "Generate data first.")
        return

    db_path = self.db_path_var.get().strip()
    if not db_path:
        self._show_error_dialog(
            "Missing DB path",
            _gui_error(
                "Generate / Preview / Export / SQLite panel",
                "SQLite DB path is required",
                "choose a SQLite database file path",
            ),
        )
        return

    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Invalid project", str(exc))
        return

    self._set_running(True, "Creating tables and inserting rows into SQLite…")

    def work():
        try:
            create_tables(db_path, self.project)
            counts = insert_project_rows(db_path, self.project, self.generated_rows, chunk_size=5000)
            self._post_ui_callback(lambda: self._on_sqlite_ok(db_path, counts))
        except Exception as exc:
            logger.exception("SQLite insert failed: %s", exc)
            msg = str(exc)
            self._post_ui_callback(lambda m=msg: self._on_job_failed(m))

    threading.Thread(target=work, daemon=True).start()

def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
    self._set_running(False, "SQLite insert complete.")
    total_rows = sum(counts.values())
    self._notify(
        f"SQLite insert complete: {total_rows} rows inserted into '{db_path}'.",
        level="success",
        duration_ms=4200,
    )

def _clear_generated(self) -> None:
    self.generated_rows = {}
    self.preview_table_combo["values"] = []
    self.preview_table_var.set("")
    self._preview_column_preferences.clear()
    self._clear_preview_tree()
    self.status_var.set("Cleared generated data.")

def _on_job_failed(self, msg: str) -> None:
    self._set_running(False, "Failed.")
    self._show_error_dialog("Error", msg)

def _make_sample_project(self, n: int = 10) -> SchemaProject:
    """
    Return a copy of the current project with root table row_counts set to n.
    Child tables keep their existing row_count (generator typically ignores it for child tables anyway).
    """
    child_tables = {fk.child_table for fk in self.project.foreign_keys}

    new_tables: list[TableSpec] = []
    for t in self.project.tables:
        rc = t.row_count
        business_key_unique_count = t.business_key_unique_count
        if t.table_name not in child_tables:
            rc = n
            if business_key_unique_count is not None:
                business_key_unique_count = min(business_key_unique_count, rc)
        new_tables.append(
            TableSpec(
                table_name=t.table_name,
                row_count=rc,
                columns=t.columns,
                business_key=t.business_key,
                business_key_unique_count=business_key_unique_count,
                business_key_static_columns=t.business_key_static_columns,
                business_key_changing_columns=t.business_key_changing_columns,
                scd_mode=t.scd_mode,
                scd_tracked_columns=t.scd_tracked_columns,
                scd_active_from_column=t.scd_active_from_column,
                scd_active_to_column=t.scd_active_to_column,
                correlation_groups=t.correlation_groups,
            )
        )

    return SchemaProject(
        name=self.project.name,
        seed=self.project.seed,
        tables=new_tables,
        foreign_keys=self.project.foreign_keys,
        timeline_constraints=self.project.timeline_constraints,
        data_quality_profiles=self.project.data_quality_profiles,
        sample_profile_fits=self.project.sample_profile_fits,
        locale_identity_bundles=self.project.locale_identity_bundles,
    )

def _on_generate_sample(self) -> None:
    if self.is_running:
        return

    if self.last_validation_errors > 0:
        self._show_error_dialog(
            "Cannot generate",
            _gui_error(
                "Generate sample action",
                "schema has validation errors",
                "run validation and resolve all error cells first",
            ),
        )
        return

    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)
    except Exception as exc:
        self._show_error_dialog("Invalid project", str(exc))
        return

    sample_project = self._make_sample_project(10)

    self._set_running(True, "Generating sample data (10 rows per root table)…")

    def work():
        try:
            rows = generate_project_rows(sample_project)
            self._post_ui_callback(lambda: self._on_generated_ok(rows))
        except Exception as exc:
            logger.exception("Sample generation failed: %s", exc)
            msg = str(exc)  # capture for Python 3.13 (exception var lifetime)
            self._post_ui_callback(lambda m=msg: self._on_job_failed(m))

    threading.Thread(target=work, daemon=True).start()

