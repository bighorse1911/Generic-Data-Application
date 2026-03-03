from __future__ import annotations



def _refresh_inline_validation_summary(self, issues: list[ValidationIssue]) -> None:
    entries: list[InlineValidationEntry] = []
    for issue in issues:
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

    if payload.scope == "fk":
        self._jump_to_fk_issue(payload.table, payload.column)
        return
    self._jump_to_table_or_column_issue(payload.table, payload.column)

def _jump_to_table_or_column_issue(self, table_name: str | None, column_name: str | None) -> None:
    if table_name is None:
        return
    self.tables_section.expand()
    self.table_editor_section.expand()
    for index, table in enumerate(self.project.tables):
        if table.table_name != table_name:
            continue
        self.tables_list.selection_clear(0, tk.END)
        self.tables_list.selection_set(index)
        self.tables_list.activate(index)
        self.tables_list.see(index)
        self._on_table_selected()
        if column_name:
            for item in self.columns_tree.get_children():
                values = self.columns_tree.item(item, "values")
                if values and str(values[0]) == column_name:
                    self.columns_tree.selection_set(item)
                    self.columns_tree.focus(item)
                    self.columns_tree.see(item)
                    self._on_column_selected()
                    break
        self.status_var.set(
            f"Jumped to validation location: table '{table_name}'"
            + (f", column '{column_name}'." if column_name else ".")
        )
        return
    self.status_var.set(
        f"Validation jump: table '{table_name}' was not found. "
        "Fix: run validation again to refresh issue locations."
    )

def _jump_to_fk_issue(self, child_table: str | None, child_column: str | None) -> None:
    if child_table is None:
        return
    self.relationships_section.expand()
    for item in self.fks_tree.get_children():
        values = self.fks_tree.item(item, "values")
        if len(values) < 4:
            continue
        table_value = str(values[2])
        column_value = str(values[3])
        if table_value != child_table:
            continue
        if child_column is not None and column_value != child_column:
            continue
        self.fks_tree.selection_set(item)
        self.fks_tree.focus(item)
        self.fks_tree.see(item)
        self.status_var.set(f"Jumped to validation location: FK '{table_value}.{column_value}'.")
        return
    self.status_var.set(
        f"Validation jump: FK '{child_table}.{child_column or ''}' was not found. "
        "Fix: run validation again to refresh issue locations."
    )

def _on_validation_heatmap_info(self, title: str, message: str) -> None:
    self._notify(f"{title}: {message}", level="info", duration_ms=5200)

def _find_dependency_cycle(self, columns: list[ColumnSpec]) -> list[str] | None:
    graph: dict[str, list[str]] = {c.name: list(c.depends_on or []) for c in columns}
    visited: set[str] = set()
    visiting: set[str] = set()

    def walk(node: str, path: list[str]) -> list[str] | None:
        if node in visiting:
            if node in path:
                idx = path.index(node)
                return path[idx:] + [node]
            return [node, node]
        if node in visited:
            return None
        visiting.add(node)
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue
            cycle = walk(dep, path)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for col in graph:
        cycle = walk(col, [])
        if cycle:
            return cycle
    return None

def _validate_project_detailed(self, project: SchemaProject) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Canonical validator remains authoritative and fail-fast.
    try:
        validate_project(project)
    except Exception as exc:
        issues.append(ValidationIssue("error", "project", None, None, str(exc)))

    table_names = [t.table_name for t in project.tables]

    # Per-table checks for richer heatmap coverage.
    for t in project.tables:
        col_map = {c.name: c for c in t.columns}
        incoming = [fk for fk in project.foreign_keys if fk.child_table == t.table_name]

        if not any(c.primary_key for c in t.columns):
            issues.append(
                ValidationIssue(
                    "error",
                    "table",
                    t.table_name,
                    None,
                    _gui_error(
                        f"Table '{t.table_name}'",
                        "no primary key column found",
                        "add one int column with primary_key=true",
                    ),
                )
            )

        names = [c.name for c in t.columns]
        if len(names) != len(set(names)):
            issues.append(
                ValidationIssue(
                    "error",
                    "table",
                    t.table_name,
                    None,
                    _gui_error(
                        f"Table '{t.table_name}'",
                        "duplicate column names found",
                        "rename columns so each column name is unique",
                    ),
                )
            )

        for c in t.columns:
            if c.primary_key and c.nullable:
                issues.append(
                    ValidationIssue(
                        "warn",
                        "column",
                        t.table_name,
                        c.name,
                        _gui_error(
                            f"Table '{t.table_name}', column '{c.name}'",
                            "primary key should not be nullable",
                            "set nullable=false for primary key columns",
                        ),
                    )
                )
            if c.primary_key and c.dtype != "int":
                issues.append(
                    ValidationIssue(
                        "warn",
                        "column",
                        t.table_name,
                        c.name,
                        _gui_error(
                            f"Table '{t.table_name}', column '{c.name}'",
                            "primary key dtype is not int",
                            "use dtype='int' for primary key columns",
                        ),
                    )
                )
            if c.dtype == "float":
                issues.append(
                    ValidationIssue(
                        "warn",
                        "column",
                        t.table_name,
                        c.name,
                        "Column uses legacy dtype 'float'. Fix: prefer dtype='decimal' for new columns.",
                    )
                )

            depends_on = list(c.depends_on or [])
            if len(depends_on) != len(set(depends_on)):
                issues.append(
                    ValidationIssue(
                        "warn",
                        "dependency",
                        t.table_name,
                        c.name,
                        _gui_error(
                            f"Table '{t.table_name}', column '{c.name}'",
                            "depends_on contains duplicate column names",
                            "list each dependency only once",
                        ),
                    )
                )
            for dep in depends_on:
                if dep == c.name:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "dependency",
                            t.table_name,
                            c.name,
                            _gui_error(
                                f"Table '{t.table_name}', column '{c.name}'",
                                "depends_on cannot reference itself",
                                "remove self references from depends_on",
                            ),
                        )
                    )
                elif dep not in col_map:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "dependency",
                            t.table_name,
                            c.name,
                            _gui_error(
                                f"Table '{t.table_name}', column '{c.name}'",
                                f"depends_on references unknown column '{dep}'",
                                "use existing columns in depends_on",
                            ),
                        )
                    )

        cycle = self._find_dependency_cycle(t.columns)
        if cycle:
            cycle_display = " -> ".join(cycle)
            issues.append(
                ValidationIssue(
                    "error",
                    "dependency",
                    t.table_name,
                    None,
                    _gui_error(
                        f"Table '{t.table_name}'",
                        f"circular depends_on detected ({cycle_display})",
                        "remove circular depends_on references",
                    ),
                )
            )

        scd_mode = (t.scd_mode or "").strip().lower() if isinstance(t.scd_mode, str) else ""
        if scd_mode in {"scd1", "scd2"} and not t.business_key:
            issues.append(
                ValidationIssue(
                    "error",
                    "scd",
                    t.table_name,
                    None,
                    _gui_error(
                        f"Table '{t.table_name}'",
                        f"scd_mode='{scd_mode}' requires business_key",
                        "configure business_key columns before enabling SCD",
                    ),
                )
            )

        unique_count = t.business_key_unique_count
        if unique_count is not None:
            if isinstance(unique_count, bool) or not isinstance(unique_count, int):
                issues.append(
                    ValidationIssue(
                        "error",
                        "scd",
                        t.table_name,
                        None,
                        _gui_error(
                            f"Table '{t.table_name}'",
                            "business_key_unique_count must be an integer when provided",
                            "set a positive whole number for business_key_unique_count or clear it",
                        ),
                    )
                )
            else:
                if unique_count <= 0:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "scd",
                            t.table_name,
                            None,
                            _gui_error(
                                f"Table '{t.table_name}'",
                                "business_key_unique_count must be > 0",
                                "set business_key_unique_count to a positive whole number",
                            ),
                        )
                    )
                if not t.business_key:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "scd",
                            t.table_name,
                            None,
                            _gui_error(
                                f"Table '{t.table_name}'",
                                "business_key_unique_count requires business_key",
                                "configure business_key columns before setting business_key_unique_count",
                            ),
                        )
                    )
                if t.row_count > 0 and unique_count > t.row_count:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "scd",
                            t.table_name,
                            None,
                            _gui_error(
                                f"Table '{t.table_name}'",
                                f"business_key_unique_count ({unique_count}) cannot exceed row_count ({t.row_count})",
                                "set business_key_unique_count <= row_count, or increase row_count",
                            ),
                        )
                    )
                if scd_mode == "scd1" and t.row_count > 0 and unique_count != t.row_count:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "scd",
                            t.table_name,
                            None,
                            _gui_error(
                                f"Table '{t.table_name}'",
                                "SCD1 requires one row per business key, so business_key_unique_count must equal row_count",
                                "set business_key_unique_count equal to row_count for SCD1 tables",
                            ),
                        )
                    )

        if t.business_key_static_columns and t.business_key_changing_columns:
            overlap = sorted(set(t.business_key_static_columns) & set(t.business_key_changing_columns))
            if overlap:
                overlap_display = ", ".join(overlap)
                issues.append(
                    ValidationIssue(
                        "error",
                        "scd",
                        t.table_name,
                        None,
                        _gui_error(
                            f"Table '{t.table_name}'",
                            f"business_key_static_columns and business_key_changing_columns overlap ({overlap_display})",
                            "put each column in only one business-key behavior list",
                        ),
                    )
                )

        if scd_mode == "scd2":
            if not t.scd_active_from_column or not t.scd_active_to_column:
                issues.append(
                    ValidationIssue(
                        "error",
                        "scd",
                        t.table_name,
                        None,
                        _gui_error(
                            f"Table '{t.table_name}'",
                            "scd_mode='scd2' requires scd_active_from_column and scd_active_to_column",
                            "set both active period columns to existing date/datetime columns",
                        ),
                    )
                )
            else:
                start = col_map.get(t.scd_active_from_column)
                end = col_map.get(t.scd_active_to_column)
                if start is None or end is None:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "scd",
                            t.table_name,
                            None,
                            _gui_error(
                                f"Table '{t.table_name}'",
                                "SCD2 active period columns were not found",
                                "set scd_active_from_column/scd_active_to_column to existing columns",
                            ),
                        )
                    )
                else:
                    if start.dtype not in {"date", "datetime"} or end.dtype not in {"date", "datetime"}:
                        issues.append(
                            ValidationIssue(
                                "error",
                                "scd",
                                t.table_name,
                                None,
                                _gui_error(
                                    f"Table '{t.table_name}'",
                                    "SCD2 active period columns must be dtype date or datetime",
                                    "use date/datetime columns for scd_active_from_column and scd_active_to_column",
                                ),
                            )
                        )
                    if start.dtype != end.dtype:
                        issues.append(
                            ValidationIssue(
                                "error",
                                "scd",
                                t.table_name,
                                None,
                                _gui_error(
                                    f"Table '{t.table_name}'",
                                    "SCD2 active period column dtypes must match",
                                    "use the same dtype for scd_active_from_column and scd_active_to_column",
                                ),
                            )
                        )
            if incoming:
                issues.append(
                    ValidationIssue(
                        "warn",
                        "scd",
                        t.table_name,
                        None,
                        _gui_error(
                            f"Table '{t.table_name}'",
                            "SCD2 is enabled on a child table with incoming FKs",
                            "keep FK max_children high enough for version growth or reduce SCD2 churn",
                        ),
                    )
                )

    for fk in project.foreign_keys:
        if fk.parent_table not in table_names:
            issues.append(
                ValidationIssue(
                    "error",
                    "fk",
                    fk.child_table,
                    fk.child_column,
                    _gui_error(
                        f"FK '{fk.child_table}.{fk.child_column}'",
                        f"parent table '{fk.parent_table}' not found",
                        "choose an existing parent table",
                    ),
                )
            )
        if fk.child_table not in table_names:
            issues.append(
                ValidationIssue(
                    "error",
                    "fk",
                    fk.child_table,
                    fk.child_column,
                    _gui_error(
                        f"FK '{fk.child_table}.{fk.child_column}'",
                        f"child table '{fk.child_table}' not found",
                        "choose an existing child table",
                    ),
                )
            )
        if fk.min_children > fk.max_children:
            issues.append(
                ValidationIssue(
                    "error",
                    "fk",
                    fk.child_table,
                    fk.child_column,
                    _gui_error(
                        f"FK '{fk.child_table}.{fk.child_column}'",
                        "min_children cannot exceed max_children",
                        "set min_children <= max_children",
                    ),
                )
            )

    return issues

def _run_validation(self) -> None:
    try:
        self._apply_project_vars_to_model()
    except Exception as exc:
        self._show_error_dialog("Project error", str(exc))
        return

    issues = self._validate_project_detailed(self.project)

    checks = ["PK", "Columns", "Dependencies", "Generator", "SCD/BK", "FKs"]
    tables = [t.table_name for t in self.project.tables]
    if any(i.table is None for i in issues):
        tables = ["Project"] + tables

    # Default OK everywhere
    status: dict[tuple[str, str], str] = {(t, c): "ok" for t in tables for c in checks}
    details: dict[tuple[str, str], list[str]] = {}

    def mark(table: str, check: str, sev: str, msg: str) -> None:
        key = (table, check)
        # escalate: ok < warn < error
        rank = {"ok": 0, "warn": 1, "error": 2}
        if rank[sev] > rank[status.get(key, "ok")]:
            status[key] = sev
        details.setdefault(key, []).append(msg)

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
        if "correlation" in text:
            return "Generator"
        if "generator" in text or "params." in text:
            return "Generator"
        if "foreign key" in text or text.startswith("fk "):
            return "FKs"
        if "primary key" in text or " pk" in text:
            return "PK"
        return "Columns"

    for iss in issues:
        target_table = iss.table if iss.table is not None else "Project"
        if target_table not in tables:
            continue
        mark(target_table, classify_bucket(iss), iss.severity, iss.message)


    # Update heatmap
    self.heatmap.set_data(tables=tables, checks=checks, status=status, details=details)
    refresh_inline = getattr(self, "_refresh_inline_validation_summary", None)
    if callable(refresh_inline):
        try:
            refresh_inline(issues)
        except TypeError:
            refresh_inline()

    # Summary
    e = sum(1 for i in issues if i.severity == "error")
    w = sum(1 for i in issues if i.severity == "warn")
    self.last_validation_errors = e
    self.last_validation_warnings = w
    self.validation_summary_var.set(f"Validation: {e} errors, {w} warnings. Click cells for details.")
    self._update_generate_enabled()

