from __future__ import annotations

def _current_schema_design_mode(self) -> SchemaDesignMode:
    return normalize_schema_design_mode(self.schema_design_mode_var.get())


def _set_schema_design_mode(self, mode: object, *, emit_feedback: bool, persist: bool) -> None:
    normalized = normalize_schema_design_mode(mode)
    current_var = normalize_schema_design_mode(self.schema_design_mode_var.get())
    if current_var != normalized:
        self._schema_design_mode_suspended = True
        try:
            self.schema_design_mode_var.set(normalized)
        finally:
            self._schema_design_mode_suspended = False
    self._apply_schema_design_mode_ui(emit_feedback=emit_feedback, persist=persist)


def _on_schema_design_mode_changed(self, *_args) -> None:
    if getattr(self, "_schema_design_mode_suspended", False):
        return
    self._set_schema_design_mode(self.schema_design_mode_var.get(), emit_feedback=True, persist=True)


def _mode_allowed_generators_for_dtype(self, dtype: str) -> list[str]:
    valid = list(valid_generators_for_dtype(dtype))
    allowed = set(allowed_generators_for_mode(self._current_schema_design_mode()))
    visible = [name for name in valid if name in allowed]

    # Preserve selected valid generator even if hidden by current mode.
    selected = self.col_generator_var.get().strip()
    if selected and selected in valid and selected not in visible:
        visible.append(selected)
    return visible


def _set_grid_group_visible(widget: object, visible: bool) -> None:
    if widget is None:
        return
    if visible:
        try:
            widget.grid()
            return
        except Exception:
            pass
        try:
            widget.pack()
        except Exception:
            return
        return
    try:
        widget.grid_remove()
        return
    except Exception:
        pass
    try:
        widget.pack_forget()
    except Exception:
        return


def _project_has_advanced_values(self) -> bool:
    raw_values = (
        self.project_timeline_constraints_var.get().strip(),
        self.project_data_quality_profiles_var.get().strip(),
        self.project_sample_profile_fits_var.get().strip(),
        self.project_locale_identity_bundles_var.get().strip(),
    )
    if any(value != "" for value in raw_values):
        return True
    project = getattr(self, "project", None)
    if project is None:
        return False
    return bool(
        getattr(project, "timeline_constraints", None)
        or getattr(project, "data_quality_profiles", None)
        or getattr(project, "sample_profile_fits", None)
        or getattr(project, "locale_identity_bundles", None)
    )


def _table_has_medium_values(table: TableSpec) -> bool:
    return bool(
        table.business_key
        or table.business_key_unique_count is not None
        or table.business_key_static_columns
        or table.business_key_changing_columns
        or (table.scd_mode or "").strip() != ""
    )


def _table_has_complex_values(table: TableSpec) -> bool:
    return bool(
        table.scd_tracked_columns
        or (table.scd_active_from_column or "").strip() != ""
        or (table.scd_active_to_column or "").strip() != ""
        or table.correlation_groups
    )


def _project_has_out_of_mode_generators(self, mode: SchemaDesignMode) -> bool:
    allowed = set(allowed_generators_for_mode(mode))
    for table in self.project.tables:
        for column in table.columns:
            generator = (column.generator or "").strip()
            if generator == "":
                continue
            if generator not in allowed:
                return True
    return False


def _collect_hidden_mode_value_labels(self, mode: SchemaDesignMode) -> list[str]:
    labels: list[str] = []

    if mode in {"simple", "medium"} and self._project_has_advanced_values():
        labels.append("project advanced settings")

    if mode == "simple":
        if any(self._table_has_medium_values(table) for table in self.project.tables):
            labels.append("table medium settings")
        if any(self._table_has_complex_values(table) for table in self.project.tables):
            labels.append("table complex settings")
    elif mode == "medium":
        if any(self._table_has_complex_values(table) for table in self.project.tables):
            labels.append("table complex settings")

    if self._project_has_out_of_mode_generators(mode):
        labels.append("hidden generator selections")

    return labels


def _apply_schema_design_mode_ui(self, *, emit_feedback: bool, persist: bool) -> None:
    mode = self._current_schema_design_mode()
    previous = getattr(self, "_schema_design_mode_last_applied", mode)

    is_simple = mode == "simple"
    is_medium = mode == "medium"
    is_complex = mode == "complex"

    self._set_grid_group_visible(getattr(self, "project_complex_group", None), is_complex)
    self._set_grid_group_visible(getattr(self, "table_mode_medium_group", None), is_medium or is_complex)
    self._set_grid_group_visible(getattr(self, "table_mode_complex_group", None), is_complex)
    self._set_grid_group_visible(getattr(self, "columns_mode_medium_group", None), is_medium or is_complex)
    self._set_grid_group_visible(getattr(self, "relationships_mode_medium_group", None), is_medium or is_complex)

    self._refresh_generator_options_for_dtype()
    self._refresh_onboarding_hints()

    if emit_feedback:
        hidden = self._collect_hidden_mode_value_labels(mode)
        if is_mode_downgrade(previous, mode):
            if hidden:
                details = ", ".join(hidden)
                self.set_status(
                    f"{mode.title()} mode applied; preserved hidden values: {details}. "
                    "Fix: switch back to a higher mode to edit those fields."
                )
            else:
                self.set_status(f"{mode.title()} mode applied.")
        else:
            self.set_status(f"{mode.title()} mode applied.")

    self._schema_design_mode_last_applied = mode
    if persist:
        self._persist_workspace_state()
