from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _focus_table_search(self) -> None:
    if hasattr(self, "tables_search"):
        self.tables_search.focus()


def _focus_columns_search(self) -> None:
    if hasattr(self, "columns_search"):
        self.columns_search.focus()


def _focus_fk_search(self) -> None:
    if hasattr(self, "fk_search"):
        self.fk_search.focus()


def _focus_next_anchor(self) -> None:
    self.focus_controller.focus_next()


def _focus_previous_anchor(self) -> None:
    self.focus_controller.focus_previous()


def _show_shortcuts_help(self) -> None:
    self.shortcut_manager.show_help_dialog(title="Schema Project Shortcuts")


def _show_notifications_history(self) -> None:
    if hasattr(self, "toast_center"):
        self.toast_center.show_history_dialog(title="Schema Project Notifications")


def _show_toast(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
    if hasattr(self, "toast_center"):
        self.toast_center.notify(message, level=level, duration_ms=duration_ms)


def _refresh_tables_list(self) -> None:
    SchemaProjectDesignerScreen._refresh_tables_list(self)
    self._refresh_onboarding_hints()


def _on_tables_search_change(self, query: str) -> None:
    q = query.strip().lower()
    if q == "":
        return
    for idx, table in enumerate(self.project.tables):
        if q in table.table_name.lower():
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(idx)
            self.tables_list.activate(idx)
            self.tables_list.see(idx)
            self._on_table_selected()
            return
    self.set_status(
        f"Tables search: no match for '{query.strip()}'. "
        "Fix: adjust the search text or clear the search."
    )


def _on_columns_search_change(self, query: str) -> None:
    self._columns_filter_page_index = 0
    self._columns_filter_rows = self._filter_index_rows(self._columns_filter_index, query)
    self._render_columns_filter_page()


def _on_fk_search_change(self, query: str) -> None:
    self._fk_filter_page_index = 0
    self._fk_filter_rows = self._filter_index_rows(self._fk_filter_index, query)
    self._render_fk_filter_page()


def _filter_index_rows(rows: list[IndexedFilterRow], query: str) -> list[IndexedFilterRow]:
    q = query.strip().lower()
    if q == "":
        return list(rows)
    tokens = [token for token in q.split() if token]
    if not tokens:
        return list(rows)
    return [row for row in rows if all(token in row.search_text for token in tokens)]


def _render_indexed_rows(tree: ttk.Treeview, rows: list[IndexedFilterRow]) -> None:
    for item in tree.get_children():
        tree.delete(item)
    for row in rows:
        tree.insert("", tk.END, values=row.values, tags=(str(row.source_index),))


def _page_window(total_rows: int, page_index: int, page_size: int) -> tuple[int, int, int, int]:
    if total_rows <= 0:
        return 0, 0, 0, 0
    total_pages = (total_rows + page_size - 1) // page_size
    normalized_page = min(max(0, page_index), total_pages - 1)
    start = normalized_page * page_size
    end = min(total_rows, start + page_size)
    return start, end, total_pages, normalized_page


def _render_columns_filter_page(self) -> None:
    start, end, total_pages, normalized_page = self._page_window(
        len(self._columns_filter_rows),
        self._columns_filter_page_index,
        FILTER_PAGE_SIZE,
    )
    self._columns_filter_page_index = normalized_page
    visible = self._columns_filter_rows[start:end]
    self._render_indexed_rows(self.columns_tree, visible)
    if not self._columns_filter_rows:
        self.columns_page_var.set("No matching columns.")
        self.columns_prev_btn.configure(state=tk.DISABLED)
        self.columns_next_btn.configure(state=tk.DISABLED)
        return
    self.columns_page_var.set(
        f"Rows {start + 1}-{end} of {len(self._columns_filter_rows)} "
        f"(page {normalized_page + 1}/{total_pages})"
    )
    self.columns_prev_btn.configure(state=(tk.NORMAL if normalized_page > 0 else tk.DISABLED))
    self.columns_next_btn.configure(
        state=(tk.NORMAL if normalized_page + 1 < total_pages else tk.DISABLED)
    )


def _render_fk_filter_page(self) -> None:
    start, end, total_pages, normalized_page = self._page_window(
        len(self._fk_filter_rows),
        self._fk_filter_page_index,
        FILTER_PAGE_SIZE,
    )
    self._fk_filter_page_index = normalized_page
    visible = self._fk_filter_rows[start:end]
    self._render_indexed_rows(self.fks_tree, visible)
    if not self._fk_filter_rows:
        self.fks_page_var.set("No matching relationships.")
        self.fks_prev_btn.configure(state=tk.DISABLED)
        self.fks_next_btn.configure(state=tk.DISABLED)
        return
    self.fks_page_var.set(
        f"Rows {start + 1}-{end} of {len(self._fk_filter_rows)} "
        f"(page {normalized_page + 1}/{total_pages})"
    )
    self.fks_prev_btn.configure(state=(tk.NORMAL if normalized_page > 0 else tk.DISABLED))
    self.fks_next_btn.configure(
        state=(tk.NORMAL if normalized_page + 1 < total_pages else tk.DISABLED)
    )


def _on_columns_filter_prev_page(self) -> None:
    if not self._columns_filter_rows:
        return
    self._columns_filter_page_index -= 1
    self._render_columns_filter_page()


def _on_columns_filter_next_page(self) -> None:
    if not self._columns_filter_rows:
        return
    self._columns_filter_page_index += 1
    self._render_columns_filter_page()


def _on_fk_filter_prev_page(self) -> None:
    if not self._fk_filter_rows:
        return
    self._fk_filter_page_index -= 1
    self._render_fk_filter_page()


def _on_fk_filter_next_page(self) -> None:
    if not self._fk_filter_rows:
        return
    self._fk_filter_page_index += 1
    self._render_fk_filter_page()


def _show_column_source_index(self, source_index: int) -> None:
    for pos, row in enumerate(self._columns_filter_rows):
        if row.source_index != source_index:
            continue
        self._columns_filter_page_index = pos // FILTER_PAGE_SIZE
        self._render_columns_filter_page()
        for item in self.columns_tree.get_children():
            tags = self.columns_tree.item(item, "tags")
            if tags and str(tags[0]) == str(source_index):
                self.columns_tree.selection_set(item)
                self.columns_tree.focus(item)
                self.columns_tree.see(item)
                return
        return


def _show_fk_source_index(self, source_index: int) -> None:
    for pos, row in enumerate(self._fk_filter_rows):
        if row.source_index != source_index:
            continue
        self._fk_filter_page_index = pos // FILTER_PAGE_SIZE
        self._render_fk_filter_page()
        for item in self.fks_tree.get_children():
            tags = self.fks_tree.item(item, "tags")
            if tags and str(tags[0]) == str(source_index):
                self.fks_tree.selection_set(item)
                self.fks_tree.focus(item)
                self.fks_tree.see(item)
                return
        return


def _refresh_columns_tree(self) -> None:
    self._columns_filter_index = []
    if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
        table = self.project.tables[self.selected_table_index]
        for idx, col in enumerate(table.columns):
            values = (
                col.name,
                col.dtype,
                col.nullable,
                col.primary_key,
                col.unique,
                col.min_value,
                col.max_value,
                ", ".join(col.choices) if col.choices else "",
                col.pattern or "",
            )
            search_text = " ".join(str(v).lower() for v in (values[0], values[1], values[5], values[6], values[7], values[8]))
            self._columns_filter_index.append(
                IndexedFilterRow(
                    source_index=idx,
                    values=values,
                    search_text=search_text,
                )
            )
    query = self.columns_search.query_var.get() if hasattr(self, "columns_search") else ""
    self._columns_filter_rows = self._filter_index_rows(self._columns_filter_index, query)
    self._columns_filter_page_index = 0
    self._render_columns_filter_page()
    self._refresh_onboarding_hints()


def _refresh_fks_tree(self) -> None:
    self._fk_filter_index = []
    for idx, fk in enumerate(self.project.foreign_keys):
        dist = fk.child_count_distribution
        dist_label = ""
        if isinstance(dist, dict):
            dist_type = str(dist.get("type", "")).strip().lower()
            if dist_type == "poisson":
                dist_label = f"poisson(lambda={dist.get('lambda')})"
            elif dist_type == "zipf":
                dist_label = f"zipf(s={dist.get('s')})"
            elif dist_type == "uniform":
                dist_label = "uniform"
            elif dist_type:
                dist_label = dist_type
        values = (
            fk.parent_table,
            fk.parent_column,
            fk.child_table,
            fk.child_column,
            fk.min_children,
            fk.max_children,
            dist_label,
        )
        search_text = " ".join(str(v).lower() for v in values)
        self._fk_filter_index.append(
            IndexedFilterRow(
                source_index=idx,
                values=values,
                search_text=search_text,
            )
        )
    query = self.fk_search.query_var.get() if hasattr(self, "fk_search") else ""
    self._fk_filter_rows = self._filter_index_rows(self._fk_filter_index, query)
    self._fk_filter_page_index = 0
    self._render_fk_filter_page()
    self._refresh_onboarding_hints()


def _on_fk_selection_changed(self, _event=None) -> None:
    self._sync_fk_defaults()
