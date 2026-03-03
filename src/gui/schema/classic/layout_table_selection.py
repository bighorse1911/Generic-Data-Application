from __future__ import annotations


def _set_table_editor_enabled(self, enabled: bool) -> None:
    state = tk.NORMAL if enabled else tk.DISABLED

    self.table_name_entry.configure(state=state)
    self.row_count_entry.configure(state=state)
    self.table_business_key_unique_count_entry.configure(state=state)
    self.table_business_key_entry.configure(state=state)
    self.table_business_key_static_entry.configure(state=state)
    self.table_business_key_changing_entry.configure(state=state)
    self.table_scd_mode_combo.configure(state=("readonly" if enabled else tk.DISABLED))
    self.table_scd_tracked_entry.configure(state=state)
    self.table_scd_active_from_entry.configure(state=state)
    self.table_scd_active_to_entry.configure(state=state)
    self.table_correlation_groups_entry.configure(state=state)
    self.table_correlation_groups_editor_btn.configure(state=state)
    self.apply_table_btn.configure(state=state)

    self.col_name_entry.configure(state=state)
    self.col_dtype_combo.configure(state=("readonly" if enabled else tk.DISABLED))
    self.col_nullable_chk.configure(state=state)
    self.col_pk_chk.configure(state=state)
    self.col_unique_chk.configure(state=state)
    self.col_min_entry.configure(state=state)
    self.col_max_entry.configure(state=state)
    self.col_choices_entry.configure(state=state)
    self.col_pattern_entry.configure(state=state)
    self.col_pattern_preset_combo.configure(state=("readonly" if enabled else tk.DISABLED))
    self.col_generator_combo.configure(state=("readonly" if enabled else tk.DISABLED))
    self.col_params_entry.configure(state=state)
    self.col_params_template_btn.configure(state=state)
    self.col_depends_entry.configure(state=state)
    self.add_col_btn.configure(state=state)
    self.edit_col_btn.configure(state=state)
    if hasattr(self, "fk_parent_selection_entry"):
        self.fk_parent_selection_entry.configure(state=state)
    if hasattr(self, "fk_child_count_distribution_entry"):
        self.fk_child_count_distribution_entry.configure(state=state)

def _refresh_tables_list(self) -> None:
    self.tables_list.delete(0, tk.END)
    for t in self.project.tables:
        self.tables_list.insert(tk.END, t.table_name)

def _on_table_selected(self, _event=None) -> None:
    sel = self.tables_list.curselection()
    if not sel:
        self.selected_table_index = None
        self._set_table_editor_enabled(False)
        self._clear_column_editor()
        self._refresh_columns_tree()
        return
    self.selected_table_index = int(sel[0])
    self._load_selected_table_into_editor()

def _load_selected_table_into_editor(self) -> None:
    if self.selected_table_index is None:
        return
    t = self.project.tables[self.selected_table_index]
    self.table_name_var.set(t.table_name)
    self.row_count_var.set(str(t.row_count))
    self.table_business_key_unique_count_var.set(
        str(t.business_key_unique_count) if t.business_key_unique_count is not None else ""
    )
    self.table_business_key_var.set(", ".join(t.business_key) if t.business_key else "")
    self.table_business_key_static_columns_var.set(
        ", ".join(t.business_key_static_columns) if t.business_key_static_columns else ""
    )
    self.table_business_key_changing_columns_var.set(
        ", ".join(t.business_key_changing_columns) if t.business_key_changing_columns else ""
    )
    self.table_scd_mode_var.set((t.scd_mode or "").strip().lower())
    self.table_scd_tracked_columns_var.set(", ".join(t.scd_tracked_columns) if t.scd_tracked_columns else "")
    self.table_scd_active_from_var.set(t.scd_active_from_column or "")
    self.table_scd_active_to_var.set(t.scd_active_to_column or "")
    self.table_correlation_groups_var.set(
        json.dumps(t.correlation_groups, sort_keys=True) if t.correlation_groups else ""
    )
    self._set_table_editor_enabled(True)
    self._refresh_columns_tree()

