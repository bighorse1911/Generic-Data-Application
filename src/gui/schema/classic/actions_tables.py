from __future__ import annotations



def _add_table(self) -> None:
    before_project = self.project
    try:
        self._apply_project_vars_to_model()
        base_name = "new_table"
        existing = {t.table_name for t in self.project.tables}
        n = 1
        name = base_name
        while name in existing:
            n += 1
            name = f"{base_name}_{n}"

        new_table = TableSpec(
            table_name=name,
            row_count=100,
            columns=[
                ColumnSpec(name=f"{name}_id", dtype="int", nullable=False, primary_key=True),
            ],
        )

        tables = list(self.project.tables) + [new_table]
        new_project = SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=tables,
            foreign_keys=self.project.foreign_keys,
            timeline_constraints=self.project.timeline_constraints,
            data_quality_profiles=self.project.data_quality_profiles,
            sample_profile_fits=self.project.sample_profile_fits,
            locale_identity_bundles=self.project.locale_identity_bundles,
        )
        validate_project(new_project)

        self.project = new_project
        self._refresh_tables_list()

        self.selected_table_index = len(self.project.tables) - 1
        self.tables_list.selection_clear(0, tk.END)
        self.tables_list.selection_set(self.selected_table_index)
        self.tables_list.activate(self.selected_table_index)
        self._load_selected_table_into_editor()

        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

        self.status_var.set(f"Added table '{name}'.")
        self._mark_dirty_if_project_changed(before_project, reason="table changes")
    except Exception as exc:
        self._show_error_dialog("Add table failed", str(exc))
    self._run_validation()

def _remove_table(self) -> None:
    if self.selected_table_index is None:
        return
    before_project = self.project
    try:
        idx = self.selected_table_index
        removed = self.project.tables[idx].table_name

        # remove any FK where this table is parent or child
        fks = [fk for fk in self.project.foreign_keys if fk.parent_table != removed and fk.child_table != removed]

        tables = list(self.project.tables)
        tables.pop(idx)

        new_project = SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=tables,
            foreign_keys=fks,
            timeline_constraints=self.project.timeline_constraints,
            data_quality_profiles=self.project.data_quality_profiles,
            sample_profile_fits=self.project.sample_profile_fits,
            locale_identity_bundles=self.project.locale_identity_bundles,
        )
        validate_project(new_project)

        self.project = new_project
        self.selected_table_index = None
        self._refresh_tables_list()
        self._refresh_columns_tree()
        self._set_table_editor_enabled(False)

        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

        self.status_var.set(f"Removed table '{removed}'.")
        self._mark_dirty_if_project_changed(before_project, reason="table changes")
    except Exception as exc:
        self._show_error_dialog("Remove table failed", str(exc))

    self._run_validation()

def _apply_table_changes(self) -> None:
    if self.selected_table_index is None:
        return
    before_project = self.project
    try:
        self._apply_project_vars_to_model()

        idx = self.selected_table_index
        old = self.project.tables[idx]

        new_name = self.table_name_var.get().strip()
        if not new_name:
            raise ValueError(
                _gui_error(
                    "Table editor / Name",
                    "table name cannot be empty",
                    "enter a non-empty table name",
                )
            )

        try:
            row_count = int(self.row_count_var.get().strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _gui_error(
                    "Table editor / Root row count",
                    f"row_count '{self.row_count_var.get()}' must be an integer",
                    "enter a whole number for Root row count",
                )
            ) from exc
        business_key_unique_count_raw = self.table_business_key_unique_count_var.get().strip()
        business_key_unique_count: int | None = None
        if business_key_unique_count_raw != "":
            try:
                business_key_unique_count = int(business_key_unique_count_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _gui_error(
                        "Table editor / Unique business keys",
                        f"business_key_unique_count '{self.table_business_key_unique_count_var.get()}' must be an integer",
                        "enter a whole number for Unique business keys or leave it blank",
                    )
                ) from exc
        location = f"Table '{new_name}' / Table editor"
        business_key = self._parse_column_name_csv(
            self.table_business_key_var.get(),
            location=location,
            field_name="business_key",
        )
        business_key_static_columns = self._parse_column_name_csv(
            self.table_business_key_static_columns_var.get(),
            location=location,
            field_name="business_key_static_columns",
        )
        business_key_changing_columns = self._parse_column_name_csv(
            self.table_business_key_changing_columns_var.get(),
            location=location,
            field_name="business_key_changing_columns",
        )
        scd_mode_raw = self.table_scd_mode_var.get().strip().lower()
        if scd_mode_raw not in {"", "scd1", "scd2"}:
            raise ValueError(
                f"{location}: unsupported scd_mode '{self.table_scd_mode_var.get()}'. "
                "Fix: choose 'scd1', 'scd2', or leave it empty."
            )
        scd_mode = scd_mode_raw or None
        scd_tracked_columns = self._parse_column_name_csv(
            self.table_scd_tracked_columns_var.get(),
            location=location,
            field_name="scd_tracked_columns",
        )
        scd_active_from_column = self._parse_optional_column_name(
            self.table_scd_active_from_var.get(),
            location=location,
            field_name="scd_active_from_column",
        )
        scd_active_to_column = self._parse_optional_column_name(
            self.table_scd_active_to_var.get(),
            location=location,
            field_name="scd_active_to_column",
        )
        correlation_groups = self._parse_table_correlation_groups(
            self.table_correlation_groups_var.get(),
            location=location,
        )

        ## We now allow for auto-sizing of children
        # if row_count <= 0:
        #     raise ValueError("Row count must be > 0.")

        # rename references in existing foreign keys
        fks = []
        for fk in self.project.foreign_keys:
            fks.append(
                ForeignKeySpec(
                    child_table=(new_name if fk.child_table == old.table_name else fk.child_table),
                    child_column=fk.child_column,
                    parent_table=(new_name if fk.parent_table == old.table_name else fk.parent_table),
                    parent_column=fk.parent_column,
                    min_children=fk.min_children,
                    max_children=fk.max_children,
                    parent_selection=fk.parent_selection,
                    child_count_distribution=fk.child_count_distribution,
                )
            )

        tables = list(self.project.tables)
        tables[idx] = TableSpec(
            table_name=new_name,
            columns=old.columns,
            row_count=row_count,
            business_key=business_key,
            business_key_unique_count=business_key_unique_count,
            business_key_static_columns=business_key_static_columns,
            business_key_changing_columns=business_key_changing_columns,
            scd_mode=scd_mode,
            scd_tracked_columns=scd_tracked_columns,
            scd_active_from_column=scd_active_from_column,
            scd_active_to_column=scd_active_to_column,
            correlation_groups=correlation_groups,
        )

        new_project = SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=tables,
            foreign_keys=fks,
            timeline_constraints=self.project.timeline_constraints,
            data_quality_profiles=self.project.data_quality_profiles,
            sample_profile_fits=self.project.sample_profile_fits,
            locale_identity_bundles=self.project.locale_identity_bundles,
        )
        validate_project(new_project)

        self.project = new_project
        self._refresh_tables_list()
        self.tables_list.selection_clear(0, tk.END)
        self.tables_list.selection_set(idx)

        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

        self.status_var.set("Applied table changes.")
        self._mark_dirty_if_project_changed(before_project, reason="table properties")
    except Exception as exc:
        self._show_error_dialog("Apply failed", str(exc))

    self._run_validation()

