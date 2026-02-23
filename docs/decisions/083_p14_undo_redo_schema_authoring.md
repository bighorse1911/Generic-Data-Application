# 083 - P14 Undo/Redo Schema Authoring

## Context
- Priority P14 in `NEXT_DECISIONS.md` required safer recovery from schema-authoring mistakes.
- `schema_project_v2` previously applied table/column/FK/SCD edits directly without reversible command history.
- Large iterative edits increased recovery cost when users needed to roll back one or more recent changes.

## Decision
- Add a reusable undo module (`src/gui_kit/undo.py`) containing:
  - `UndoCommand` protocol (`label`, `do`, `undo`, `redo`),
  - `SnapshotCommand` for before/after state restoration,
  - `UndoStack` with bounded history and redo invalidation on new pushes.
- Integrate snapshot-based undo/redo into `SchemaEditorBaseScreen` for schema-authoring mutations:
  - add/remove/edit table,
  - add/edit/remove/move column,
  - add/remove relationship (FK),
  - SCD/business-key changes via table-apply flow.
- Add route controls and shortcuts:
  - explicit `Undo` / `Redo` actions in project panel,
  - `Ctrl/Cmd+Z` for undo,
  - `Ctrl/Cmd+Y` and `Ctrl/Cmd+Shift+Z` for redo.
- Keep save/load semantics stable:
  - save updates clean baseline for dirty tracking,
  - load resets undo/redo history to loaded project baseline.

## Consequences
- Users can recover from recent schema-authoring mistakes without manual reconstruction.
- Undo/redo operations restore both project model and relevant selection context while re-running full validation for consistency.
- Dirty-state indicator now syncs against a saved-project baseline after undo/redo transitions.
- Regression coverage added:
  - `tests/test_gui_kit_undo.py` for stack behavior,
  - `tests/test_gui_undo_redo.py` for table/column/FK/SCD undo/redo flows in `schema_project_v2`.
