from __future__ import annotations



def _open_project_timeline_constraints_editor(self) -> None:
    JsonEditorDialog(
        self,
        title="Timeline Constraints JSON Editor",
        initial_text=self.project_timeline_constraints_var.get().strip() or "[]",
        require_object=False,
        on_apply=self._on_project_timeline_constraints_json_apply,
    )

def _on_project_timeline_constraints_json_apply(self, pretty_json: str) -> None:
    self.project_timeline_constraints_var.set(pretty_json)
    self.status_var.set("Applied timeline constraints JSON.")

def _open_project_data_quality_profiles_editor(self) -> None:
    JsonEditorDialog(
        self,
        title="Data Quality Profiles JSON Editor",
        initial_text=self.project_data_quality_profiles_var.get().strip() or "[]",
        require_object=False,
        on_apply=self._on_project_data_quality_profiles_json_apply,
    )

def _on_project_data_quality_profiles_json_apply(self, pretty_json: str) -> None:
    self.project_data_quality_profiles_var.set(pretty_json)
    self.status_var.set("Applied data quality profiles JSON.")

def _open_project_sample_profile_fits_editor(self) -> None:
    JsonEditorDialog(
        self,
        title="Sample Profile Fits JSON Editor",
        initial_text=self.project_sample_profile_fits_var.get().strip() or "[]",
        require_object=False,
        on_apply=self._on_project_sample_profile_fits_json_apply,
    )

def _on_project_sample_profile_fits_json_apply(self, pretty_json: str) -> None:
    self.project_sample_profile_fits_var.set(pretty_json)
    self.status_var.set("Applied sample profile fits JSON.")

def _open_project_locale_identity_bundles_editor(self) -> None:
    JsonEditorDialog(
        self,
        title="Locale Identity Bundles JSON Editor",
        initial_text=self.project_locale_identity_bundles_var.get().strip() or "[]",
        require_object=False,
        on_apply=self._on_project_locale_identity_bundles_json_apply,
    )

def _on_project_locale_identity_bundles_json_apply(self, pretty_json: str) -> None:
    self.project_locale_identity_bundles_var.set(pretty_json)
    self.status_var.set("Applied locale identity bundles JSON.")

def _parse_table_correlation_groups(
    self,
    raw_value: str,
    *,
    location: str,
) -> list[dict[str, object]] | None:
    value = raw_value.strip()
    if value == "":
        return None
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise ValueError(
            f"{location}: correlation_groups JSON is invalid ({exc}). "
            "Fix: provide a valid JSON list of correlation-group objects."
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"{location}: correlation_groups must be a JSON list. "
            "Fix: use a list like [{\"group_id\": \"g1\", \"columns\": [\"a\", \"b\"], \"rank_correlation\": [[1, 0.8], [0.8, 1]]}]."
        )
    groups: list[dict[str, object]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(
                f"{location}: correlation_groups[{idx}] must be a JSON object. "
                "Fix: provide each correlation group as an object."
            )
        groups.append(dict(item))
    return groups

def _parse_project_timeline_constraints(
    self,
    raw_value: str,
    *,
    location: str,
) -> list[dict[str, object]] | None:
    value = raw_value.strip()
    if value == "":
        return None
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise ValueError(
            f"{location}: timeline_constraints JSON is invalid ({exc}). "
            "Fix: provide a valid JSON list of timeline-constraint rule objects."
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"{location}: timeline_constraints must be a JSON list. "
            "Fix: use a list like [{\"rule_id\": \"dg03_rule\", \"child_table\": \"orders\", \"child_column\": \"ordered_at\", \"references\": [...]}]."
        )
    rules: list[dict[str, object]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(
                f"{location}: timeline_constraints[{idx}] must be a JSON object. "
                "Fix: provide each timeline rule as an object."
            )
        rules.append(dict(item))
    return rules

def _parse_project_data_quality_profiles(
    self,
    raw_value: str,
    *,
    location: str,
) -> list[dict[str, object]] | None:
    value = raw_value.strip()
    if value == "":
        return None
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise ValueError(
            f"{location}: data_quality_profiles JSON is invalid ({exc}). "
            "Fix: provide a valid JSON list of DG06 profile objects."
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"{location}: data_quality_profiles must be a JSON list. "
            "Fix: use a list like [{\"profile_id\": \"mcar_orders\", \"table\": \"orders\", \"column\": \"note\", \"kind\": \"missingness\", \"mechanism\": \"mcar\", \"base_rate\": 0.1}]."
        )
    profiles: list[dict[str, object]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(
                f"{location}: data_quality_profiles[{idx}] must be a JSON object. "
                "Fix: provide each DG06 profile as an object."
            )
        profiles.append(dict(item))
    return profiles

def _parse_project_sample_profile_fits(
    self,
    raw_value: str,
    *,
    location: str,
) -> list[dict[str, object]] | None:
    value = raw_value.strip()
    if value == "":
        return None
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise ValueError(
            f"{location}: sample_profile_fits JSON is invalid ({exc}). "
            "Fix: provide a valid JSON list of DG07 sample-profile-fit objects."
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"{location}: sample_profile_fits must be a JSON list. "
            "Fix: use a list like [{\"fit_id\": \"orders_amount_fit\", \"table\": \"orders\", \"column\": \"amount\", \"sample_source\": {\"path\": \"tests/fixtures/sample.csv\", \"column_index\": 0}}]."
        )
    fits: list[dict[str, object]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(
                f"{location}: sample_profile_fits[{idx}] must be a JSON object. "
                "Fix: provide each DG07 fit as an object."
            )
        fits.append(dict(item))
    return fits

def _parse_project_locale_identity_bundles(
    self,
    raw_value: str,
    *,
    location: str,
) -> list[dict[str, object]] | None:
    value = raw_value.strip()
    if value == "":
        return None
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise ValueError(
            f"{location}: locale_identity_bundles JSON is invalid ({exc}). "
            "Fix: provide a valid JSON list of DG09 locale-bundle objects."
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"{location}: locale_identity_bundles must be a JSON list. "
            "Fix: use a list like [{\"bundle_id\": \"customer_identity\", \"base_table\": \"customers\", \"columns\": {\"first_name\": \"first_name\", \"postcode\": \"postcode\"}}]."
        )
    bundles: list[dict[str, object]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(
                f"{location}: locale_identity_bundles[{idx}] must be a JSON object. "
                "Fix: provide each DG09 bundle as an object."
            )
        bundles.append(dict(item))
    return bundles

def _apply_project_vars_to_model(self) -> None:
    name = self.project_name_var.get().strip()
    try:
        seed = int(self.seed_var.get().strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _gui_error(
                "Project / Seed",
                f"seed '{self.seed_var.get()}' must be an integer",
                "enter a whole number for Seed",
            )
        ) from exc
    timeline_constraints = self._parse_project_timeline_constraints(
        self.project_timeline_constraints_var.get(),
        location="Project / Timeline constraints",
    )
    data_quality_profiles = self._parse_project_data_quality_profiles(
        self.project_data_quality_profiles_var.get(),
        location="Project / Data quality profiles",
    )
    sample_profile_fits = self._parse_project_sample_profile_fits(
        self.project_sample_profile_fits_var.get(),
        location="Project / Sample profile fits",
    )
    locale_identity_bundles = self._parse_project_locale_identity_bundles(
        self.project_locale_identity_bundles_var.get(),
        location="Project / Locale identity bundles",
    )
    self.project = SchemaProject(
        name=name,
        seed=seed,
        tables=self.project.tables,
        foreign_keys=self.project.foreign_keys,
        timeline_constraints=timeline_constraints,
        data_quality_profiles=data_quality_profiles,
        sample_profile_fits=sample_profile_fits,
        locale_identity_bundles=locale_identity_bundles,
    )

def _save_project(self) -> bool:
    try:
        self._apply_project_vars_to_model()
        validate_project(self.project)

        path = filedialog.asksaveasfilename(
            title="Save project as JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return False
        save_project_to_json(self.project, path)
        self.status_var.set(f"Saved project: {path}")
        self._mark_clean()
        return True
    except Exception as exc:
        self._show_error_dialog("Save failed", str(exc))
        return False

def _load_project(self, *, confirm_unsaved: bool = True) -> None:
    if confirm_unsaved and not self._confirm_discard_or_save("loading another project"):
        return
    try:
        path = filedialog.askopenfilename(
            title="Load project JSON",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        project = load_project_from_json(path)
        self.project = project
        self._suspend_dirty_tracking = True
        self.project_name_var.set(project.name)
        self.seed_var.set(str(project.seed))
        self.project_timeline_constraints_var.set(
            json.dumps(project.timeline_constraints, sort_keys=True) if project.timeline_constraints else ""
        )
        self.project_data_quality_profiles_var.set(
            json.dumps(project.data_quality_profiles, sort_keys=True) if project.data_quality_profiles else ""
        )
        self.project_sample_profile_fits_var.set(
            json.dumps(project.sample_profile_fits, sort_keys=True) if project.sample_profile_fits else ""
        )
        self.project_locale_identity_bundles_var.set(
            json.dumps(project.locale_identity_bundles, sort_keys=True) if project.locale_identity_bundles else ""
        )
        self._suspend_dirty_tracking = False

        self.selected_table_index = None
        self._refresh_tables_list()
        self._refresh_columns_tree()
        self._set_table_editor_enabled(False)

        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()
        self._preview_column_preferences.clear()
        self._clear_preview_tree()
        self._mark_clean()
        self._run_validation()

        self.status_var.set(f"Loaded project: {path}")
    except Exception as exc:
        self._suspend_dirty_tracking = False
        self._show_error_dialog("Load failed", str(exc))

