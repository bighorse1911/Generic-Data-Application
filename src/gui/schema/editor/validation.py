from __future__ import annotations

def _refresh_inline_validation_summary(self, issues: list[ValidationIssue] | None = None) -> None:
    if not hasattr(self, "inline_validation"):
        return

    entries: list[InlineValidationEntry] = []
    issue_list = issues if issues is not None else self._validate_project_detailed(self.project)
    for issue in issue_list:
        location = "Project"
        if issue.scope == "fk":
            fk_table = issue.table or "unknown_child"
            fk_column = issue.column or "unknown_column"
            location = f"FK {fk_table}.{fk_column}"
        elif issue.table is not None and issue.column is not None:
            location = f"Table '{issue.table}', column '{issue.column}'"
        elif issue.table is not None:
            location = f"Table '{issue.table}'"
        entries.append(
            InlineValidationEntry(
                severity=issue.severity,
                location=location,
                message=issue.message,
                jump_payload=issue,
            )
        )
    self.inline_validation.set_entries(entries)


def _jump_to_validation_issue(self, entry: InlineValidationEntry) -> None:
    payload = entry.jump_payload
    if not isinstance(payload, ValidationIssue):
        return

    self.main_tabs.select(self.schema_tab)
    if payload.scope == "fk":
        self._jump_to_fk_issue(payload.table, payload.column)
        return
    self._jump_to_table_or_column_issue(payload.table, payload.column)


def _jump_to_table_or_column_issue(self, table_name: str | None, column_name: str | None) -> None:
    if table_name is None:
        return

    for index, table in enumerate(self.project.tables):
        if table.table_name != table_name:
            continue

        self.tables_panel.expand()
        self.columns_panel.expand()
        self.tables_list.selection_clear(0, tk.END)
        self.tables_list.selection_set(index)
        self.tables_list.activate(index)
        self.tables_list.see(index)
        self._on_table_selected()
        if column_name:
            col_idx = next((i for i, col in enumerate(self.project.tables[index].columns) if col.name == column_name), None)
            if col_idx is not None:
                if hasattr(self, "columns_search") and self.columns_search.query_var.get().strip():
                    self.columns_search.query_var.set("")
                    self._on_columns_search_change("")
                self._show_column_source_index(col_idx)
                if self.columns_tree.selection():
                    self._on_column_selected()
        self.set_status(
            f"Jumped to validation location: table '{table_name}'"
            + (f", column '{column_name}'." if column_name else ".")
        )
        return

    self.set_status(
        f"Validation jump: table '{table_name}' was not found. "
        "Fix: re-run validation to refresh issue locations."
    )


def _jump_to_fk_issue(self, child_table: str | None, child_column: str | None) -> None:
    self.relationships_panel.expand()
    if child_table is None:
        return
    target_index: int | None = None
    for idx, fk in enumerate(self.project.foreign_keys):
        if fk.child_table != child_table:
            continue
        if child_column is not None and fk.child_column != child_column:
            continue
        target_index = idx
        break
    if target_index is not None:
        if hasattr(self, "fk_search") and self.fk_search.query_var.get().strip():
            self.fk_search.query_var.set("")
            self._on_fk_search_change("")
        self._show_fk_source_index(target_index)
        if self.fks_tree.selection():
            row = self.project.foreign_keys[target_index]
            self.set_status(
                f"Jumped to validation location: FK '{row.child_table}.{row.child_column}'."
            )
            return
    self.set_status(
        f"Validation jump: FK '{child_table}.{child_column or ''}' was not found. "
        "Fix: re-run validation to refresh issue locations."
    )


def _cancel_validation_debounce(self) -> None:
    if self._validation_debounce_after_id is None:
        return
    try:
        self.after_cancel(self._validation_debounce_after_id)
    except tk.TclError:
        pass
    finally:
        self._validation_debounce_after_id = None
        self._validation_pending_tables.clear()
        self._validation_pending_mode = "full"


def _stage_incremental_validation(self, *, table_names: Iterable[str]) -> None:
    clean_names = {name.strip() for name in table_names if isinstance(name, str) and name.strip() != ""}
    if not clean_names:
        return
    self._validation_pending_mode = "incremental"
    self._validation_pending_tables.update(clean_names)


def _stage_full_validation(self) -> None:
    self._validation_pending_mode = "full"
    self._validation_pending_tables.clear()


def _run_validation_full(self) -> None:
    self._run_validation(mode="full")


def _run_validation(self, *, mode: str = "auto") -> None:
    normalized_mode = str(mode).strip().lower()
    if normalized_mode not in {"auto", "full", "incremental"}:
        normalized_mode = "auto"

    if normalized_mode == "full":
        self._cancel_validation_debounce()
        self._execute_full_validation()
        return

    if normalized_mode == "incremental":
        tables = set(self._validation_pending_tables)
        self._validation_pending_tables.clear()
        self._validation_pending_mode = "full"
        if tables:
            self._schedule_incremental_validation(tables)
        else:
            self._execute_full_validation()
        return

    if self._validation_pending_mode == "incremental" and self._validation_pending_tables:
        tables = set(self._validation_pending_tables)
        self._validation_pending_tables.clear()
        self._validation_pending_mode = "full"
        self._schedule_incremental_validation(tables)
        return

    self._validation_pending_mode = "full"
    self._validation_pending_tables.clear()
    self._cancel_validation_debounce()
    self._execute_full_validation()


def _schedule_incremental_validation(self, table_names: set[str]) -> None:
    if not table_names:
        self._execute_full_validation()
        return
    self._validation_pending_tables.update(table_names)
    if self._validation_debounce_after_id is not None:
        return
    self.validation_summary_var.set("Validation: updating...")
    self._validation_debounce_after_id = self.after(
        VALIDATION_DEBOUNCE_MS,
        self._flush_incremental_validation,
    )


def _flush_incremental_validation(self) -> None:
    self._validation_debounce_after_id = None
    tables = set(self._validation_pending_tables)
    self._validation_pending_tables.clear()
    if not tables:
        self._execute_full_validation()
        return
    self._execute_incremental_validation(tables)


def _execute_full_validation(self) -> None:
    try:
        self._apply_project_vars_to_model()
    except Exception as exc:
        self._show_error_dialog("Project error", str(exc))
        return
    issues = self._validate_project_detailed(self.project)
    self._rebuild_validation_cache(issues)
    self._apply_validation_issues(issues)


def _execute_incremental_validation(self, touched_tables: set[str]) -> None:
    if not self._validation_cache_table_issues and not self._validation_cache_project_issues:
        self._execute_full_validation()
        return
    try:
        self._apply_project_vars_to_model()
    except Exception as exc:
        self._show_error_dialog("Project error", str(exc))
        return

    expanded_tables = self._expand_incremental_scope_tables(touched_tables)
    if not expanded_tables:
        self._execute_full_validation()
        return

    projection = self._build_validation_projection(expanded_tables)
    issues = self._validate_project_detailed(projection)
    grouped = self._group_issues_by_table(issues)
    current_table_names = {table.table_name for table in self.project.tables}

    for stale in list(self._validation_cache_table_issues.keys()):
        if stale not in current_table_names:
            self._validation_cache_table_issues.pop(stale, None)
    for table_name in expanded_tables:
        if table_name in current_table_names:
            self._validation_cache_table_issues[table_name] = grouped.get(table_name, [])

    merged = self._merge_validation_cache()
    self._apply_validation_issues(merged)


def _expand_incremental_scope_tables(self, touched_tables: set[str]) -> set[str]:
    existing_names = {table.table_name for table in self.project.tables}
    base = {name for name in touched_tables if name in existing_names}
    if not base:
        return set()
    expanded = set(base)
    for fk in self.project.foreign_keys:
        if fk.child_table in base or fk.parent_table in base:
            if fk.child_table in existing_names:
                expanded.add(fk.child_table)
            if fk.parent_table in existing_names:
                expanded.add(fk.parent_table)
    return expanded


def _build_validation_projection(self, table_names: set[str]) -> SchemaProject:
    # Preserve original table order for deterministic projected validation.
    ordered_tables = [table for table in self.project.tables if table.table_name in table_names]
    projected_fks = [
        fk
        for fk in self.project.foreign_keys
        if fk.child_table in table_names and fk.parent_table in table_names
    ]
    projected_timeline_constraints: list[dict[str, object]] | None = None
    raw_rules = self.project.timeline_constraints or []
    if raw_rules:
        projected_rules: list[dict[str, object]] = []
        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                continue
            child_table = str(raw_rule.get("child_table", "")).strip()
            if child_table not in table_names:
                continue
            references_raw = raw_rule.get("references")
            if not isinstance(references_raw, list):
                continue
            filtered_references = [
                dict(reference)
                for reference in references_raw
                if isinstance(reference, dict)
                and str(reference.get("parent_table", "")).strip() in table_names
            ]
            if not filtered_references:
                continue
            rule_copy = dict(raw_rule)
            rule_copy["references"] = filtered_references
            projected_rules.append(rule_copy)
        if projected_rules:
            projected_timeline_constraints = projected_rules
    projected_data_quality_profiles: list[dict[str, object]] | None = None
    raw_profiles = self.project.data_quality_profiles or []
    if raw_profiles:
        projected_profiles: list[dict[str, object]] = []
        for raw_profile in raw_profiles:
            if not isinstance(raw_profile, dict):
                continue
            profile_table = str(raw_profile.get("table", "")).strip()
            if profile_table not in table_names:
                continue
            projected_profiles.append(dict(raw_profile))
        if projected_profiles:
            projected_data_quality_profiles = projected_profiles
    projected_sample_profile_fits: list[dict[str, object]] | None = None
    raw_fits = self.project.sample_profile_fits or []
    if raw_fits:
        projected_fits: list[dict[str, object]] = []
        for raw_fit in raw_fits:
            if not isinstance(raw_fit, dict):
                continue
            fit_table = str(raw_fit.get("table", "")).strip()
            if fit_table not in table_names:
                continue
            projected_fits.append(dict(raw_fit))
        if projected_fits:
            projected_sample_profile_fits = projected_fits
    projected_locale_identity_bundles: list[dict[str, object]] | None = None
    raw_locale_bundles = self.project.locale_identity_bundles or []
    if raw_locale_bundles:
        projected_bundles: list[dict[str, object]] = []
        for raw_bundle in raw_locale_bundles:
            if not isinstance(raw_bundle, dict):
                continue
            base_table = str(raw_bundle.get("base_table", "")).strip()
            if base_table not in table_names:
                continue
            bundle_copy = dict(raw_bundle)
            related_raw = raw_bundle.get("related_tables")
            if isinstance(related_raw, list):
                filtered_related = [
                    dict(item)
                    for item in related_raw
                    if isinstance(item, dict)
                    and str(item.get("table", "")).strip() in table_names
                ]
                if filtered_related:
                    bundle_copy["related_tables"] = filtered_related
                else:
                    bundle_copy.pop("related_tables", None)
            projected_bundles.append(bundle_copy)
        if projected_bundles:
            projected_locale_identity_bundles = projected_bundles
    return SchemaProject(
        name=self.project.name,
        seed=self.project.seed,
        tables=ordered_tables,
        foreign_keys=projected_fks,
        timeline_constraints=projected_timeline_constraints,
        data_quality_profiles=projected_data_quality_profiles,
        sample_profile_fits=projected_sample_profile_fits,
        locale_identity_bundles=projected_locale_identity_bundles,
    )


def _group_issues_by_table(issues: list[ValidationIssue]) -> dict[str, list[ValidationIssue]]:
    grouped: dict[str, list[ValidationIssue]] = {}
    for issue in issues:
        if issue.table is None:
            continue
        grouped.setdefault(issue.table, []).append(issue)
    return grouped


def _rebuild_validation_cache(self, issues: list[ValidationIssue]) -> None:
    grouped = self._group_issues_by_table(issues)
    self._validation_cache_project_issues = [issue for issue in issues if issue.table is None]
    self._validation_cache_table_issues = {
        table.table_name: grouped.get(table.table_name, [])
        for table in self.project.tables
    }


def _merge_validation_cache(self) -> list[ValidationIssue]:
    merged = list(self._validation_cache_project_issues)
    for table in self.project.tables:
        merged.extend(self._validation_cache_table_issues.get(table.table_name, []))
    return merged


def _apply_validation_issues(self, issues: list[ValidationIssue]) -> None:
    checks = ["PK", "Columns", "Dependencies", "Generator", "SCD/BK", "FKs"]
    tables = [table.table_name for table in self.project.tables]
    if any(issue.table is None for issue in issues):
        tables = ["Project"] + tables

    status: dict[tuple[str, str], str] = {(table, check): "ok" for table in tables for check in checks}
    details: dict[tuple[str, str], list[str]] = {}

    def mark(table: str, check: str, severity: str, message: str) -> None:
        key = (table, check)
        rank = {"ok": 0, "warn": 1, "error": 2}
        if rank.get(severity, 0) > rank.get(status.get(key, "ok"), 0):
            status[key] = severity
        details.setdefault(key, []).append(message)

    def classify_bucket(issue: ValidationIssue) -> str:
        if issue.scope == "fk":
            return "FKs"
        if issue.scope == "dependency":
            return "Dependencies"
        if issue.scope == "scd":
            return "SCD/BK"
        if issue.scope == "generator":
            return "Generator"

        text = issue.message.lower()
        if "depends_on" in text or "dependency" in text:
            return "Dependencies"
        if "scd" in text or "business_key" in text:
            return "SCD/BK"
        if "generator" in text or "params." in text:
            return "Generator"
        if "foreign key" in text or text.startswith("fk "):
            return "FKs"
        if "primary key" in text or " pk" in text:
            return "PK"
        return "Columns"

    for issue in issues:
        target_table = issue.table if issue.table is not None else "Project"
        if target_table not in tables:
            continue
        mark(target_table, classify_bucket(issue), issue.severity, issue.message)

    self.heatmap.set_data(tables=tables, checks=checks, status=status, details=details)
    self._refresh_inline_validation_summary(issues)

    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warn")
    self.last_validation_errors = errors
    self.last_validation_warnings = warnings
    self.validation_summary_var.set(
        f"Validation: {errors} errors, {warnings} warnings. Click cells for details."
    )
    self._update_generate_enabled()
