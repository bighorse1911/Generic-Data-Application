from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _add_fk(self) -> None:
    parent = self.fk_parent_table_var.get().strip()
    child = self.fk_child_table_var.get().strip()
    staged = tuple(name for name in (parent, child) if name)
    if staged:
        self._stage_incremental_validation(table_names=staged)
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._add_fk(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Add relationship",
        reason="relationship changes",
    )


def _remove_selected_fk(self) -> None:
    staged_tables: set[str] = set()
    idx = self._selected_fk_index()
    if idx is not None and idx < len(self.project.foreign_keys):
        fk = self.project.foreign_keys[idx]
        staged_tables.add(fk.parent_table)
        staged_tables.add(fk.child_table)
    if staged_tables:
        self._stage_incremental_validation(table_names=staged_tables)
    else:
        self._stage_full_validation()
    before_state = self._capture_undo_snapshot()
    SchemaProjectDesignerScreen._remove_selected_fk(self)
    self._record_undo_snapshot(
        before=before_state,
        label="Remove relationship",
        reason="relationship changes",
    )
