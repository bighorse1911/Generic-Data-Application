from __future__ import annotations


def _refresh_columns_tree(self) -> None:
    for item in self.columns_tree.get_children():
        self.columns_tree.delete(item)

    if self.selected_table_index is None:
        return

    t = self.project.tables[self.selected_table_index]
    for i, c in enumerate(t.columns):
        self.columns_tree.insert(
            "",
            tk.END,
            values=(
                c.name, c.dtype, c.nullable, c.primary_key, c.unique,
                c.min_value, c.max_value,
                ", ".join(c.choices) if c.choices else "",
                c.pattern or "",
            ),
            tags=(str(i),),
        )

def _selected_column_index(self) -> int | None:
    sel = self.columns_tree.selection()
    if not sel:
        return None
    return int(self.columns_tree.item(sel[0], "tags")[0])

def _clear_column_editor(self) -> None:
    self.col_name_var.set("")
    self.col_dtype_var.set("text")
    self.col_nullable_var.set(True)
    self.col_pk_var.set(False)
    self.col_unique_var.set(False)
    self.col_min_var.set("")
    self.col_max_var.set("")
    self.col_choices_var.set("")
    self.col_pattern_var.set("")
    self.col_pattern_preset_var.set(PATTERN_PRESET_CUSTOM)
    self.col_generator_var.set("")
    self.col_params_var.set("")
    self.col_depends_var.set("")
    self._refresh_generator_options_for_dtype()

def _load_column_into_editor(self, col: ColumnSpec) -> None:
    self.col_name_var.set(col.name)
    dtype = "decimal" if col.dtype == "float" else col.dtype
    self.col_dtype_var.set(dtype)
    self.col_nullable_var.set(bool(col.nullable))
    self.col_pk_var.set(bool(col.primary_key))
    self.col_unique_var.set(bool(col.unique))
    self.col_min_var.set("" if col.min_value is None else str(col.min_value))
    self.col_max_var.set("" if col.max_value is None else str(col.max_value))
    self.col_choices_var.set(", ".join(col.choices) if col.choices else "")
    self.col_pattern_var.set(col.pattern or "")
    self._sync_pattern_preset_from_pattern()
    self._refresh_generator_options_for_dtype()
    self.col_generator_var.set(col.generator or "")
    if isinstance(col.params, dict):
        self.col_params_var.set(json.dumps(col.params))
    else:
        self.col_params_var.set("")
    self.col_depends_var.set(", ".join(col.depends_on) if col.depends_on else "")

def _on_column_dtype_changed(self, *_args) -> None:
    self._refresh_generator_options_for_dtype()

def _on_column_generator_changed(self, *_args) -> None:
    # Placeholder hook for future generator-specific GUI widgets.
    pass

def _refresh_generator_options_for_dtype(self) -> None:
    if not hasattr(self, "col_generator_combo"):
        return
    valid = valid_generators_for_dtype(self.col_dtype_var.get())
    self.col_generator_combo.configure(values=valid)
    selected = self.col_generator_var.get().strip()
    if selected and selected not in valid:
        self.col_generator_var.set("")

def _on_pattern_entry_focus_out(self, _event=None) -> None:
    self._sync_pattern_preset_from_pattern()

def _on_pattern_preset_selected(self, _event=None) -> None:
    preset = self.col_pattern_preset_var.get().strip()
    pattern = PATTERN_PRESETS.get(preset)
    if pattern is None:
        return
    self.col_pattern_var.set(pattern)

def _sync_pattern_preset_from_pattern(self) -> None:
    pattern = self.col_pattern_var.get().strip()
    for preset, preset_pattern in PATTERN_PRESETS.items():
        if preset_pattern is None:
            continue
        if pattern == preset_pattern:
            self.col_pattern_preset_var.set(preset)
            return
    self.col_pattern_preset_var.set(PATTERN_PRESET_CUSTOM)

def _apply_generator_params_template(self) -> None:
    generator = self.col_generator_var.get().strip()
    if generator == "":
        self._show_error_dialog(
            "Params template",
            _gui_error(
                "Column editor / Generator",
                "no generator selected",
                "choose a generator before filling params",
            ),
        )
        return

    template = default_generator_params_template(generator, self.col_dtype_var.get())
    if template is None:
        self._show_error_dialog(
            "Params template",
            _gui_error(
                f"Column editor / Generator '{generator}'",
                "no params template is defined",
                "enter params JSON manually for this generator",
            ),
        )
        return

    params: dict[str, object] = {}
    existing_raw = self.col_params_var.get().strip()
    if existing_raw:
        try:
            existing = json.loads(existing_raw)
        except Exception as exc:
            self._show_error_dialog(
                "Params template",
                _gui_error(
                    "Column editor / Params JSON",
                    f"invalid JSON ({exc})",
                    "fix Params JSON or clear it before applying template",
                ),
            )
            return
        if not isinstance(existing, dict):
            self._show_error_dialog(
                "Params template",
                _gui_error(
                    "Column editor / Params JSON",
                    "value must be a JSON object",
                    "use an object like {\"min\": 0} before applying template",
                ),
            )
            return
        params.update(existing)

    for key, value in template.items():
        params.setdefault(key, value)

    self.col_params_var.set(json.dumps(params))
    self.status_var.set(f"Applied params template for generator '{generator}'.")

def _open_table_correlation_groups_editor(self) -> None:
    JsonEditorDialog(
        self,
        title="Correlation Groups JSON Editor",
        initial_text=self.table_correlation_groups_var.get().strip() or "[]",
        require_object=False,
        on_apply=self._on_table_correlation_groups_json_apply,
    )

def _on_table_correlation_groups_json_apply(self, pretty_json: str) -> None:
    self.table_correlation_groups_var.set(pretty_json)
    self.status_var.set("Applied correlation groups JSON.")

def _on_column_selected(self, _event=None) -> None:
    if self.selected_table_index is None:
        return
    col_idx = self._selected_column_index()
    if col_idx is None:
        return
    t = self.project.tables[self.selected_table_index]
    self._load_column_into_editor(t.columns[col_idx])

