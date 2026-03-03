from __future__ import annotations

def _toggle_authoring_panel(self) -> None:
        self._authoring_collapsed = not self._authoring_collapsed
        if self._authoring_collapsed:
            self.authoring_box.pack_forget()
            self.authoring_toggle_btn.configure(text="Expand schema authoring")
            return
        self.authoring_box.pack(fill="x", pady=(0, 8), before=self.diagram_box)
        self.authoring_toggle_btn.configure(text="Collapse schema authoring")


def _sync_authoring_controls_from_project(self) -> None:
        table_names = self._table_names()
        self._set_combo_values(
            self.relationship_child_table_combo,
            values=table_names,
            variable=self.relationship_child_table_var,
        )
        self._set_combo_values(
            self.relationship_parent_table_combo,
            values=table_names,
            variable=self.relationship_parent_table_var,
        )
        self._set_combo_values(
            self.edit_table_current_combo,
            values=["", *table_names],
            variable=self.edit_table_current_var,
        )
        self._set_combo_values(
            self.edit_column_table_combo,
            values=table_names,
            variable=self.edit_column_table_var,
        )
        self.column_table_var.set(self.edit_column_table_var.get().strip())
        self._on_column_table_changed()
        self._on_relationship_child_table_changed()
        self._on_relationship_parent_table_changed()
        self._on_edit_table_selected()
        self._on_edit_column_table_changed()


def _on_column_pk_changed(self) -> None:
        if not hasattr(self, "column_nullable_check"):
            return
        if self.column_primary_key_var.get():
            self.column_nullable_var.set(False)
            self.column_nullable_check.state(["disabled"])
            return
        self.column_nullable_check.state(["!disabled"])


def _on_column_table_changed(self) -> None:
        # Selection is intentionally retained; no dependent widgets currently require sync.
        _ = self.column_table_var.get().strip()


def _on_edit_table_selected(self) -> None:
        table_name = self.edit_table_current_var.get().strip()
        table = self._table_for_name(table_name)
        if table is None:
            if table_name == "":
                self.edit_table_name_var.set("")
            self.edit_table_row_count_var.set("100")
            return
        self.edit_table_name_var.set(table.table_name)
        self.edit_table_row_count_var.set(str(table.row_count))


def _on_edit_column_table_changed(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        column_names = self._columns_for_table(table_name)
        self._set_combo_values(
            self.edit_column_current_combo,
            values=["", *column_names],
            variable=self.edit_column_current_var,
        )
        self._on_edit_column_selected()


def _on_edit_column_selected(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        column_name = self.edit_column_current_var.get().strip()
        table = self._table_for_name(table_name)
        if table is None or not column_name:
            self.edit_column_name_var.set("")
            self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
            self.edit_column_primary_key_var.set(False)
            self.edit_column_nullable_var.set(True)
            self._on_edit_column_pk_changed()
            return
        selected_column = None
        for column in table.columns:
            if column.name == column_name:
                selected_column = column
                break
        if selected_column is None:
            self.edit_column_name_var.set("")
            self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
            self.edit_column_primary_key_var.set(False)
            self.edit_column_nullable_var.set(True)
            self._on_edit_column_pk_changed()
            return
        self.edit_column_name_var.set(selected_column.name)
        dtype = selected_column.dtype
        if dtype == "float":
            dtype = "decimal"
        if dtype not in ERD_AUTHORING_DTYPES:
            dtype = ERD_AUTHORING_DTYPES[0]
        self.edit_column_dtype_var.set(dtype)
        self.edit_column_primary_key_var.set(bool(selected_column.primary_key))
        self.edit_column_nullable_var.set(bool(selected_column.nullable))
        self._on_edit_column_pk_changed()


def _on_edit_column_pk_changed(self) -> None:
        if not hasattr(self, "edit_column_nullable_check"):
            return
        if self.edit_column_primary_key_var.get():
            self.edit_column_nullable_var.set(False)
            self.edit_column_nullable_check.state(["disabled"])
            return
        self.edit_column_nullable_check.state(["!disabled"])


def _reset_table_editor(self) -> None:
        self.edit_table_current_var.set("")
        self.edit_table_name_var.set("")
        self.edit_table_row_count_var.set("100")


def _reset_column_editor(self) -> None:
        self.edit_column_current_var.set("")
        self.edit_column_name_var.set("")
        self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
        self.edit_column_primary_key_var.set(False)
        self.edit_column_nullable_var.set(True)
        self._on_edit_column_pk_changed()


def _save_table_shared(self) -> None:
        current_table_name = self.edit_table_current_var.get().strip()
        new_table_name = self.edit_table_name_var.get().strip()
        try:
            if current_table_name == "":
                self.project = add_table_to_erd_project(
                    self.project,
                    table_name_value=new_table_name,
                    row_count_value=self.edit_table_row_count_var.get(),
                )
                if self.project is None:
                    return
                self.table_name_var.set(new_table_name)
                self.table_row_count_var.set(self.edit_table_row_count_var.get())
                self.edit_table_current_var.set(new_table_name)
                status_text = f"Added table '{new_table_name}'."
            else:
                self.project = update_table_in_erd_project(
                    self.project,
                    current_table_name_value=current_table_name,
                    new_table_name_value=new_table_name,
                    row_count_value=self.edit_table_row_count_var.get(),
                )
                if current_table_name != new_table_name and current_table_name in self._node_positions:
                    self._node_positions[new_table_name] = self._node_positions.pop(current_table_name)
                self.edit_table_current_var.set(new_table_name)
                status_text = f"Updated table '{current_table_name}' -> '{new_table_name}'."
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(status_text)


def _save_column_shared(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        current_column_name = self.edit_column_current_var.get().strip()
        new_column_name = self.edit_column_name_var.get().strip()
        self.column_table_var.set(table_name)
        self.column_name_var.set(new_column_name)
        self.column_dtype_var.set(self.edit_column_dtype_var.get())
        self.column_primary_key_var.set(bool(self.edit_column_primary_key_var.get()))
        self.column_nullable_var.set(bool(self.edit_column_nullable_var.get()))
        try:
            if current_column_name == "":
                self.project = add_column_to_erd_project(
                    self.project,
                    table_name_value=table_name,
                    column_name_value=new_column_name,
                    dtype_value=self.edit_column_dtype_var.get(),
                    primary_key=bool(self.edit_column_primary_key_var.get()),
                    nullable=bool(self.edit_column_nullable_var.get()),
                )
                self.edit_column_current_var.set(new_column_name)
                status_text = f"Added column '{table_name}.{new_column_name}'."
            else:
                self.project = update_column_in_erd_project(
                    self.project,
                    table_name_value=table_name,
                    current_column_name_value=current_column_name,
                    new_column_name_value=new_column_name,
                    dtype_value=self.edit_column_dtype_var.get(),
                    primary_key=bool(self.edit_column_primary_key_var.get()),
                    nullable=bool(self.edit_column_nullable_var.get()),
                )
                self.edit_column_current_var.set(new_column_name)
                status_text = (
                    f"Updated column '{table_name}.{current_column_name}' -> '{table_name}.{new_column_name}'."
                )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(status_text)


def _on_relationship_child_table_changed(self) -> None:
        child_columns = self._columns_for_table(self.relationship_child_table_var.get().strip())
        self._set_combo_values(
            self.relationship_child_column_combo,
            values=child_columns,
            variable=self.relationship_child_column_var,
        )


def _on_relationship_parent_table_changed(self) -> None:
        parent_columns = self._columns_for_table(
            self.relationship_parent_table_var.get().strip(),
            primary_key_only=True,
        )
        self._set_combo_values(
            self.relationship_parent_column_combo,
            values=parent_columns,
            variable=self.relationship_parent_column_var,
        )
