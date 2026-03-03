from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _open_params_json_editor(self) -> None:
    JsonEditorDialog(
        self,
        title="Generator Params JSON Editor",
        initial_text=self.col_params_var.get(),
        require_object=True,
        on_apply=self._on_params_json_apply,
    )


def _on_params_json_apply(self, pretty_json: str) -> None:
    self.col_params_var.set(pretty_json)
    self.set_status("Applied JSON editor content to Generator params JSON.")
    self._show_toast("Generator params updated from JSON editor.", level="success")


def _refresh_generator_options_for_dtype(self) -> None:
    if not hasattr(self, "col_generator_combo"):
        return

    mode = self._current_schema_design_mode()
    selected = self.col_generator_var.get().strip()
    full_valid = valid_generators_for_dtype(self.col_dtype_var.get())
    mode_valid = self._mode_allowed_generators_for_dtype(self.col_dtype_var.get())
    self.col_generator_combo.configure(values=mode_valid)

    if selected and selected not in full_valid:
        self.col_generator_var.set("")
        self._last_out_of_mode_generator_notice = None
        return

    allowed = set(allowed_generators_for_mode(mode))
    if selected and selected not in allowed:
        notice_key = (mode, selected)
        if notice_key != self._last_out_of_mode_generator_notice:
            self.set_status(
                f"{mode.title()} mode: generator '{selected}' is preserved for this column "
                "and remains valid, even though it is hidden from this mode's default list."
            )
            self._last_out_of_mode_generator_notice = notice_key
        return

    self._last_out_of_mode_generator_notice = None


def _apply_generator_params_template(self) -> None:
    before = self.col_params_var.get()
    SchemaProjectDesignerScreen._apply_generator_params_template(self)
    after = self.col_params_var.get()
    if after != before and after.strip() != "":
        self._show_toast("Applied generator params template.", level="success")


def _move_column_up(self) -> None:
    self._move_selected_column(-1)


def _move_column_down(self) -> None:
    self._move_selected_column(1)


def _add_column(self) -> None:
    if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
        self._stage_incremental_validation(
            table_names=(self.project.tables[self.selected_table_index].table_name,),
        )
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._add_column(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Add column",
        reason="column changes",
    )


def _apply_selected_column_changes(self) -> None:
    if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
        self._stage_incremental_validation(
            table_names=(self.project.tables[self.selected_table_index].table_name,),
        )
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._apply_selected_column_changes(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Edit column",
        reason="column changes",
    )


def _remove_selected_column(self) -> None:
    if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
        self._stage_incremental_validation(
            table_names=(self.project.tables[self.selected_table_index].table_name,),
        )
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._remove_selected_column(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Remove column",
        reason="column changes",
    )


def _move_selected_column(self, delta: int) -> None:
    if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
        self._stage_incremental_validation(
            table_names=(self.project.tables[self.selected_table_index].table_name,),
        )
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._move_selected_column(self, delta)
    self._record_undo_snapshot(
        before=before_state,
        label=("Move column up" if delta < 0 else "Move column down"),
        reason="column order",
    )
