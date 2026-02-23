# 080 - P11 Async Schema Project IO Hardening

## Context
- Priority P11 in `NEXT_DECISIONS.md` required hardening schema-project JSON Save/Load UX for large schemas.
- Existing `schema_project_v2` Save/Load callbacks executed synchronously on the UI thread.
- Large JSON read/write operations could block UI responsiveness and did not have explicit duplicate-operation guards.

## Decision
- Implement async Save/Load project JSON flows for `schema_project_v2` through `JobLifecycleController` callbacks in `SchemaEditorBaseScreen`.
- Route project-panel buttons and `Ctrl/Cmd+S`/`Ctrl/Cmd+O` shortcuts to async entrypoints:
  - `_start_save_project_async`
  - `_start_load_project_async`
- Add a dedicated project-IO lifecycle state (`project_io_lifecycle`) with:
  - busy/status feedback via progress indicator + status line,
  - duplicate-operation blocking when project IO is already running,
  - safe cancel/abort handling when file dialogs are dismissed.
- Preserve existing synchronous `_save_project` semantics for dirty-state confirmation guards so unsaved-change confirmation behavior remains deterministic and backward-compatible.

## Consequences
- User-initiated Save/Load operations no longer run full JSON IO on the UI thread.
- The route provides explicit status messages when Save/Load is canceled or blocked by an active project operation.
- Existing tests that call synchronous `_save_project`/`_load_project` directly remain compatible.
- New regression coverage (`tests/test_gui_project_io_async.py`) validates async lifecycle usage, completion behavior, cancellation behavior, and duplicate-start guards.
