from __future__ import annotations

def _preview_columns_for_table(self, table_name: str) -> list[str]:
    for table in self.project.tables:
        if table.table_name == table_name:
            return [column.name for column in table.columns]
    if self._preview_source_rows:
        return list(self._preview_source_rows[0].keys())
    return []


def _refresh_preview_projection(self) -> None:
    table_name = self._preview_source_table
    if table_name == "":
        self._clear_preview_tree()
        return

    schema_columns = self._preview_columns_for_table(table_name)
    if not schema_columns and self._preview_source_rows:
        schema_columns = list(self._preview_source_rows[0].keys())
    if not schema_columns:
        self._clear_preview_tree()
        return

    visible_columns = self._preview_column_preferences.get(table_name, list(schema_columns))
    visible_columns = [name for name in visible_columns if name in schema_columns]
    if not visible_columns:
        visible_columns = list(schema_columns)
        self._preview_column_preferences[table_name] = list(visible_columns)

    projected_rows: list[dict[str, object]] = []
    for row in self._preview_source_rows:
        projected_rows.append({name: row.get(name, "") for name in visible_columns})

    self.preview_table.set_columns(visible_columns)
    self.preview_table.set_rows(projected_rows)
    self._on_preview_page_size_changed()


def _on_preview_page_size_changed(self, _event=None) -> None:
    if not hasattr(self, "preview_table"):
        return
    try:
        page_size = int(self.preview_page_size_var.get().strip())
        self.preview_table.set_page_size(page_size)
        self._persist_workspace_state()
    except Exception as exc:
        self._show_error_dialog(
            "Preview page size",
            f"Preview page size: invalid value '{self.preview_page_size_var.get()}'. "
            f"Fix: choose one of 50, 100, 200, or 500. Details: {exc}",
        )
        self.preview_page_size_var.set(str(self.preview_table.page_size))


def _open_preview_column_chooser(self) -> None:
    table_name = self.preview_table_var.get().strip()
    if table_name == "":
        self._show_error_dialog(
            "Preview columns",
            "Preview columns: no preview table is selected. "
            "Fix: choose a preview table first.",
        )
        return

    columns = self._preview_columns_for_table(table_name)
    if not columns:
        self._show_error_dialog(
            "Preview columns",
            f"Preview columns: table '{table_name}' has no columns to configure. "
            "Fix: select a table with generated preview data.",
        )
        return

    ColumnChooserDialog(
        self,
        columns=columns,
        visible_columns=self._preview_column_preferences.get(table_name, list(columns)),
        on_apply=lambda selected: self._on_preview_columns_applied(table_name, selected),
        title=f"Preview columns: {table_name}",
    )


def _on_preview_columns_applied(self, table_name: str, selected_columns: list[str]) -> None:
    self._preview_column_preferences[table_name] = list(selected_columns)
    self._refresh_preview_projection()
    self._persist_workspace_state()
    self._show_toast("Applied preview column visibility/order.", level="success")


def _on_preview_table_selected(self, _event=None) -> None:
    self._refresh_preview()


def _refresh_preview(self) -> None:
    if not self.generated_rows:
        self._clear_preview_tree()
        self._refresh_onboarding_hints()
        return

    table = self.preview_table_var.get().strip()
    if not table or table not in self.generated_rows:
        self._clear_preview_tree()
        self._refresh_onboarding_hints()
        return

    try:
        limit = int(self.preview_limit_var.get().strip())
        if limit <= 0:
            raise ValueError
    except Exception:
        limit = 200
        self.preview_limit_var.set("200")

    self._preview_source_table = table
    self._preview_source_rows = list(self.generated_rows[table][:limit])
    self._refresh_preview_projection()
    self._refresh_onboarding_hints()


def _clear_preview_tree(self) -> None:
    self._preview_source_table = ""
    self._preview_source_rows = []
    if hasattr(self, "preview_table"):
        self.preview_table.set_columns([])
        self.preview_table.set_rows([])
    self._refresh_onboarding_hints()
