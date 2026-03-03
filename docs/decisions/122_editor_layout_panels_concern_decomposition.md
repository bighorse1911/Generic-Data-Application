# 122 - Editor Layout Panels Concern Decomposition

## Context

- `src/gui/schema/editor/layout_panels.py` remained a schema-editor readability hotspot at 635 LOC.
- `SchemaEditorBaseScreen` depends on stable wrapper names and module-context binding semantics from `editor_base.py`.
- This slice required strict no-behavior-change parity across panel layout, onboarding hints, and schema-design-mode visibility flows.

## Decision

- Decompose panel builders into same-folder concern modules:
  - `src/gui/schema/editor/layout_panels_project.py`
  - `src/gui/schema/editor/layout_panels_tables.py`
  - `src/gui/schema/editor/layout_panels_columns.py`
  - `src/gui/schema/editor/layout_panels_relationships.py`
  - `src/gui/schema/editor/layout_panels_generate.py`
- Convert `src/gui/schema/editor/layout_panels.py` into a thin compatibility hub that re-exports:
  - `build_project_panel`
  - `build_tables_panel`
  - `build_columns_panel`
  - `build_relationships_panel`
  - `build_generate_panel`
- Preserve context binding by importing new panel modules in `src/gui/schema/editor_base.py` and including them in `_bind_editor_module_context(...)`.
- Extend import-contract coverage for new panel modules in `tests/test_import_contracts.py`.

## Consequences

- Schema-editor panel layout ownership is now concern-specific and easier to navigate.
- `layout_panels.py` is reduced to a compatibility surface while `SchemaEditorBaseScreen` wrapper behavior remains unchanged.
- Targeted schema-editor tests and isolated GUI suite remain green with no observed behavior regressions.
