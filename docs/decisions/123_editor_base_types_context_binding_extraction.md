# 123 - Editor Base Types and Context-Binding Extraction

## Context

- `src/gui/schema/editor_base.py` remained slightly above the soft module-size budget and mixed wrapper methods with shared constants/types and binding plumbing.
- The schema-editor architecture depends on module-context binding for patch/import compatibility across `src/gui/schema/editor/*.py`.
- This slice required strict no-behavior-change parity while improving file navigation.

## Decision

- Extract shared editor constants and lightweight dataclasses to:
  - `src/gui/schema/editor/base_types.py`
  - (`VALIDATION_DEBOUNCE_MS`, `FILTER_PAGE_SIZE`, `UNDO_STACK_LIMIT`, `STARTER_FIXTURE_PATH`, `IndexedFilterRow`, `EditorUndoSnapshot`)
- Extract module-context binding helper and bound-module registry to:
  - `src/gui/schema/editor/context_binding.py`
  - (`EDITOR_CONTEXT_MODULE_NAMES`, `bind_editor_modules_from_scope`)
- Update `src/gui/schema/editor_base.py` to import these concerns and invoke:
  - `bind_editor_modules_from_scope(globals())`
- Keep all `SchemaEditorBaseScreen` wrapper methods unchanged.

## Consequences

- `editor_base.py` is slimmer and focused on compatibility wrappers.
- Shared editor constants/types and context-binding plumbing are now discoverable in dedicated modules.
- Import contracts, module-budget guardrails, and isolated GUI suites remain green with no observed behavior regressions.
