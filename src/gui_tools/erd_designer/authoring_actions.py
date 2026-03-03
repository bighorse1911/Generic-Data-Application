from __future__ import annotations

def _create_new_schema(self) -> None:
        try:
            self.project = new_erd_schema_project(
                name_value=self.schema_name_var.get(),
                seed_value=self.schema_seed_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self.schema_path_var.set("")
        self._node_positions = {}
        self._node_bounds = {}
        self._node_draw_order = []
        self._drag_table_name = None
        self._drag_offset = None
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(
            f"Created new schema '{self.project.name}' with seed={self.project.seed}. Add tables, columns, and relationships."
        )


def _add_table(self) -> None:
        try:
            self.project = add_table_to_erd_project(
                self.project,
                table_name_value=self.table_name_var.get(),
                row_count_value=self.table_row_count_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        table_name = self.table_name_var.get().strip()
        self.table_name_var.set("")
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Added table '{table_name}'.")


def _edit_table(self) -> None:
        current_table_name = self.edit_table_current_var.get().strip()
        new_table_name = self.edit_table_name_var.get().strip()
        try:
            self.project = update_table_in_erd_project(
                self.project,
                current_table_name_value=current_table_name,
                new_table_name_value=new_table_name,
                row_count_value=self.edit_table_row_count_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        if current_table_name != new_table_name and current_table_name in self._node_positions:
            self._node_positions[new_table_name] = self._node_positions.pop(current_table_name)
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Updated table '{current_table_name}' -> '{new_table_name}'.")


def _add_column(self) -> None:
        try:
            self.project = add_column_to_erd_project(
                self.project,
                table_name_value=self.column_table_var.get(),
                column_name_value=self.column_name_var.get(),
                dtype_value=self.column_dtype_var.get(),
                primary_key=bool(self.column_primary_key_var.get()),
                nullable=bool(self.column_nullable_var.get()),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        column_name = self.column_name_var.get().strip()
        table_name = self.column_table_var.get().strip()
        self.column_name_var.set("")
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Added column '{table_name}.{column_name}'.")


def _edit_column(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        current_column_name = self.edit_column_current_var.get().strip()
        new_column_name = self.edit_column_name_var.get().strip()
        try:
            self.project = update_column_in_erd_project(
                self.project,
                table_name_value=table_name,
                current_column_name_value=current_column_name,
                new_column_name_value=new_column_name,
                dtype_value=self.edit_column_dtype_var.get(),
                primary_key=bool(self.edit_column_primary_key_var.get()),
                nullable=bool(self.edit_column_nullable_var.get()),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Updated column '{table_name}.{current_column_name}' -> '{table_name}.{new_column_name}'.")


def _add_relationship(self) -> None:
        try:
            self.project = add_relationship_to_erd_project(
                self.project,
                child_table_value=self.relationship_child_table_var.get(),
                child_column_value=self.relationship_child_column_var.get(),
                parent_table_value=self.relationship_parent_table_var.get(),
                parent_column_value=self.relationship_parent_column_var.get(),
                min_children_value=self.relationship_min_children_var.get(),
                max_children_value=self.relationship_max_children_var.get(),
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        child_table = self.relationship_child_table_var.get().strip()
        child_column = self.relationship_child_column_var.get().strip()
        parent_table = self.relationship_parent_table_var.get().strip()
        parent_column = self.relationship_parent_column_var.get().strip()
        self._draw_erd()
        self.status_var.set(
            f"Added relationship '{child_table}.{child_column} -> {parent_table}.{parent_column}'."
        )
