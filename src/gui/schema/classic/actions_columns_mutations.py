from __future__ import annotations


def _add_column(self) -> None:
    if self.selected_table_index is None:
        return
    before_project = self.project
    try:
        self._apply_project_vars_to_model()
        idx = self.selected_table_index
        t = self.project.tables[idx]

        new_col = self._column_spec_from_editor(action_prefix="Add column")
        cols = list(t.columns)

        if any(c.name == new_col.name for c in cols):
            raise ValueError(
                _gui_error(
                    f"Table '{t.table_name}', column '{new_col.name}'",
                    "column already exists",
                    "choose a unique column name",
                )
            )

        # If setting PK, unset existing PK (MVP allows only one PK)
        if new_col.primary_key:
            if new_col.dtype != "int":
                raise ValueError(
                    _gui_error(
                        "Add column / Primary key",
                        "primary key must be dtype=int in this MVP",
                        "change dtype to 'int' or disable Primary key",
                    )
                )
            cols = [ColumnSpec(**{**c.__dict__, "primary_key": False}) for c in cols]  # type: ignore

        cols.append(new_col)

        tables = list(self.project.tables)
        tables[idx] = TableSpec(
            table_name=t.table_name,
            columns=cols,
            row_count=t.row_count,
            business_key=t.business_key,
            business_key_unique_count=t.business_key_unique_count,
            business_key_static_columns=t.business_key_static_columns,
            business_key_changing_columns=t.business_key_changing_columns,
            scd_mode=t.scd_mode,
            scd_tracked_columns=t.scd_tracked_columns,
            scd_active_from_column=t.scd_active_from_column,
            scd_active_to_column=t.scd_active_to_column,
            correlation_groups=t.correlation_groups,
        )

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

        self._clear_column_editor()

        self._refresh_columns_tree()
        self._refresh_fk_dropdowns()

        self.status_var.set("Column added.")
        self._mark_dirty_if_project_changed(before_project, reason="column changes")
    except Exception as exc:
        self._show_error_dialog("Add column failed", str(exc))
    self._run_validation()

def _apply_selected_column_changes(self) -> None:
    if self.selected_table_index is None:
        return

    before_project = self.project
    try:
        col_idx = self._selected_column_index()
        if col_idx is None:
            raise ValueError(
                _gui_error(
                    "Edit column",
                    "no column is selected",
                    "select a column in the Columns table first",
                )
            )

        self._apply_project_vars_to_model()
        t_idx = self.selected_table_index
        t = self.project.tables[t_idx]
        old_col = t.columns[col_idx]
        edited_col = self._column_spec_from_editor(action_prefix="Edit column")

        cols = list(t.columns)
        if any(i != col_idx and c.name == edited_col.name for i, c in enumerate(cols)):
            raise ValueError(
                _gui_error(
                    f"Table '{t.table_name}', column '{edited_col.name}'",
                    "column already exists",
                    "choose a unique column name",
                )
            )

        if edited_col.primary_key:
            if edited_col.dtype != "int":
                raise ValueError(
                    _gui_error(
                        "Edit column / Primary key",
                        "primary key must be dtype=int in this MVP",
                        "change dtype to 'int' or disable Primary key",
                    )
                )
            cols = [
                ColumnSpec(**{**c.__dict__, "primary_key": False}) if i != col_idx else c
                for i, c in enumerate(cols)
            ]

        cols[col_idx] = edited_col

        tables = list(self.project.tables)
        tables[t_idx] = TableSpec(
            table_name=t.table_name,
            columns=cols,
            row_count=t.row_count,
            business_key=t.business_key,
            business_key_unique_count=t.business_key_unique_count,
            business_key_static_columns=t.business_key_static_columns,
            business_key_changing_columns=t.business_key_changing_columns,
            scd_mode=t.scd_mode,
            scd_tracked_columns=t.scd_tracked_columns,
            scd_active_from_column=t.scd_active_from_column,
            scd_active_to_column=t.scd_active_to_column,
            correlation_groups=t.correlation_groups,
        )

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
        self._refresh_columns_tree()
        self._refresh_fk_dropdowns()

        children = self.columns_tree.get_children()
        if 0 <= col_idx < len(children):
            self.columns_tree.selection_set(children[col_idx])
            self.columns_tree.focus(children[col_idx])
            self._on_column_selected()

        self.status_var.set(f"Updated column '{old_col.name}'.")
        self._mark_dirty_if_project_changed(before_project, reason="column changes")
    except Exception as exc:
        self._show_error_dialog("Edit column failed", str(exc))
    self._run_validation()

def _remove_selected_column(self) -> None:
    if self.selected_table_index is None:
        return
    col_idx = self._selected_column_index()
    if col_idx is None:
        return
    before_project = self.project
    try:
        self._apply_project_vars_to_model()
        t_idx = self.selected_table_index
        t = self.project.tables[t_idx]

        cols = list(t.columns)
        removed = cols[col_idx].name

        # prevent removing a column that is used in an FK
        for fk in self.project.foreign_keys:
            if fk.child_table == t.table_name and fk.child_column == removed:
                raise ValueError(
                    _gui_error(
                        f"Remove column / Table '{t.table_name}', column '{removed}'",
                        "column is used as a child FK",
                        "remove the related FK first",
                    )
                )
            if fk.parent_table == t.table_name and fk.parent_column == removed:
                raise ValueError(
                    _gui_error(
                        f"Remove column / Table '{t.table_name}', column '{removed}'",
                        "column is referenced as a parent FK target",
                        "remove the related FK first",
                    )
                )

        cols.pop(col_idx)

        tables = list(self.project.tables)
        tables[t_idx] = TableSpec(
            table_name=t.table_name,
            columns=cols,
            row_count=t.row_count,
            business_key=t.business_key,
            business_key_unique_count=t.business_key_unique_count,
            business_key_static_columns=t.business_key_static_columns,
            business_key_changing_columns=t.business_key_changing_columns,
            scd_mode=t.scd_mode,
            scd_tracked_columns=t.scd_tracked_columns,
            scd_active_from_column=t.scd_active_from_column,
            scd_active_to_column=t.scd_active_to_column,
            correlation_groups=t.correlation_groups,
        )

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
        self._refresh_columns_tree()
        self._clear_column_editor()
        self._refresh_fk_dropdowns()
        self.status_var.set(f"Removed column '{removed}'.")
        self._mark_dirty_if_project_changed(before_project, reason="column changes")
    except Exception as exc:
        self._show_error_dialog("Remove column failed", str(exc))
    self._run_validation()

def _move_selected_column(self, delta: int) -> None:
    if self.selected_table_index is None:
        return
    col_idx = self._selected_column_index()
    if col_idx is None:
        return
    before_project = self.project
    try:
        self._apply_project_vars_to_model()
        t_idx = self.selected_table_index
        t = self.project.tables[t_idx]

        new_idx = col_idx + delta
        if new_idx < 0 or new_idx >= len(t.columns):
            return

        cols = list(t.columns)
        cols[col_idx], cols[new_idx] = cols[new_idx], cols[col_idx]

        tables = list(self.project.tables)
        tables[t_idx] = TableSpec(
            table_name=t.table_name,
            columns=cols,
            row_count=t.row_count,
            business_key=t.business_key,
            business_key_unique_count=t.business_key_unique_count,
            business_key_static_columns=t.business_key_static_columns,
            business_key_changing_columns=t.business_key_changing_columns,
            scd_mode=t.scd_mode,
            scd_tracked_columns=t.scd_tracked_columns,
            scd_active_from_column=t.scd_active_from_column,
            scd_active_to_column=t.scd_active_to_column,
            correlation_groups=t.correlation_groups,
        )

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
        self._refresh_columns_tree()
        self._refresh_fk_dropdowns()

        children = self.columns_tree.get_children()
        if 0 <= new_idx < len(children):
            self.columns_tree.selection_set(children[new_idx])
        self._mark_dirty_if_project_changed(before_project, reason="column order")

    except Exception as exc:
        self._show_error_dialog("Move column failed", str(exc))
    self._run_validation()


