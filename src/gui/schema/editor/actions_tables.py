from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _set_table_editor_enabled(self, enabled: bool) -> None:
    SchemaProjectDesignerScreen._set_table_editor_enabled(self, enabled)
    if hasattr(self, "col_params_editor_btn"):
        self.col_params_editor_btn.configure(state=(tk.NORMAL if enabled else tk.DISABLED))


def _add_table(self) -> None:
    self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._add_table(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Add table",
        reason="table changes",
    )


def _remove_table(self) -> None:
    self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._remove_table(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Remove table",
        reason="table changes",
    )


def _apply_table_changes(self) -> None:
    staged_tables: set[str] = set()
    if self.selected_table_index is not None and self.selected_table_index < len(self.project.tables):
        staged_tables.add(self.project.tables[self.selected_table_index].table_name)
    pending_name = self.table_name_var.get().strip()
    if pending_name:
        staged_tables.add(pending_name)
    if staged_tables:
        self._stage_incremental_validation(table_names=staged_tables)
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._apply_table_changes(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Apply table changes",
        reason="table properties",
    )
