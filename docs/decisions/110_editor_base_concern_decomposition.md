# 110 - Editor Base Concern Decomposition

## Context

- `src/gui/schema/editor_base.py` remained a major readability hotspot (~2.8k LOC, large method surface).
- Schema authoring flows are high-coverage and patch-sensitive across GUI tests.
- The refactor goal required no behavior changes and no import/patch contract breaks.

## Decision

- Decompose `src/gui/schema/editor_base.py` internals into concern modules under `src/gui/schema/editor/`:
  - `jobs.py`
  - `layout.py`
  - `validation.py`
  - `filters.py`
  - `preview.py`
  - `project_io.py`
  - `actions_tables.py`
  - `actions_columns.py`
  - `actions_fks.py`
  - `actions_generation.py`
  - `state_undo.py`
- Keep `SchemaEditorBaseScreen` in `src/gui/schema/editor_base.py` with the existing method names as thin wrappers.
- Keep `src.gui_schema_editor_base` compatibility behavior unchanged.
- Add explicit contract coverage for required patch-target methods via `tests/gui/test_editor_base_method_contracts.py`.
- Preserve starter fixture shortcut contract using repo-root resolution for `tests/fixtures/default_schema_project.json`.

## Consequences

- Schema-editor logic is now navigable by concern while preserving legacy method-level patch points.
- `editor_base.py` is reduced to a compatibility/wrapper surface, lowering hotspot pressure and improving maintainability.
- GUI regression stability is preserved via isolated GUI test execution and targeted parity tests.
- Remaining large-module decomposition can now focus on `classic_screen.py` and runtime hotspots.
