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

    columns = self._preview_columns_for_table(table_name)
    if not columns:
        self._clear_preview_tree()
        return

    selected_columns = self._preview_column_preferences.get(table_name, list(columns))
    selected_columns = [name for name in selected_columns if name in columns]
    if not selected_columns:
        selected_columns = list(columns)
        self._preview_column_preferences[table_name] = list(selected_columns)

    projected: list[dict[str, object]] = []
    for row in self._preview_source_rows:
        projected.append({name: row.get(name, "") for name in selected_columns})

    self.preview_table.set_columns(selected_columns)
    self.preview_table.set_rows(projected)
    self._on_preview_page_size_changed()

def _on_preview_paging_toggled(self) -> None:
    enabled = bool(self.preview_paging_enabled_var.get())
    page_size = 100
    try:
        page_size = int(self.preview_page_size_var.get().strip())
        if page_size <= 0:
            raise ValueError
    except Exception:
        page_size = 100
        self.preview_page_size_var.set("100")
        self._show_error_dialog(
            "Preview page size",
            "Generate / Preview / Export / SQLite panel: preview page size is invalid. "
            "Fix: choose one of 50, 100, 200, or 500.",
        )
    if enabled:
        self.preview_table.enable_pagination(page_size=page_size)
        self.preview_page_size_combo.configure(state="readonly")
        self.status_var.set("Preview pagination enabled.")
    else:
        self.preview_table.disable_pagination()
        self.preview_page_size_combo.configure(state=tk.DISABLED)
        self.status_var.set("Preview pagination disabled.")
    self._refresh_preview_projection()

def _on_preview_page_size_changed(self, _event=None) -> None:
    try:
        page_size = int(self.preview_page_size_var.get().strip())
        self.preview_table.set_page_size(page_size)
    except Exception:
        self.preview_page_size_var.set("100")
        self.preview_table.set_page_size(100)
        self._show_error_dialog(
            "Preview page size",
            "Generate / Preview / Export / SQLite panel: preview page size is invalid. "
            "Fix: choose one of 50, 100, 200, or 500.",
        )

def _open_preview_column_chooser(self) -> None:
    table_name = self.preview_table_var.get().strip()
    if table_name == "":
        self._show_error_dialog(
            "Preview columns",
            "Generate / Preview / Export / SQLite panel: no preview table selected. "
            "Fix: choose a preview table before configuring visible columns.",
        )
        return
    columns = self._preview_columns_for_table(table_name)
    if not columns:
        self._show_error_dialog(
            "Preview columns",
            f"Generate / Preview / Export / SQLite panel: preview table '{table_name}' has no columns. "
            "Fix: generate rows for the selected table before opening preview columns.",
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
    self.status_var.set(f"Applied preview columns for '{table_name}'.")

def _refresh_preview(self) -> None:
    if not self.generated_rows:
        self._clear_preview_tree()
        return

    table = self.preview_table_var.get().strip()
    if not table or table not in self.generated_rows:
        self._clear_preview_tree()
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

def _clear_preview_tree(self) -> None:
    self._preview_source_table = ""
    self._preview_source_rows = []
    self.preview_table.set_columns([])
    self.preview_table.set_rows([])

def _render_preview_rows(self, rows: list[dict[str, object]]) -> None:
    self.preview_table.set_rows(rows)

