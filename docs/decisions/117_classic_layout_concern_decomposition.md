# 117 - Classic Layout Concern Decomposition

## Context

- `src/gui/schema/classic/layout.py` remained a soft-budget hotspot at 854 LOC.
- The classic schema screen still depends on module-context patch semantics from `src/gui/schema/classic_screen.py`.
- This slice required strict no-behavior-change compatibility with stable `SchemaProjectDesignerScreen` wrappers and legacy shim exports.

## Decision

- Decompose classic layout concerns into same-folder modules:
  - `src/gui/schema/classic/layout_init.py`
  - `src/gui/schema/classic/layout_build.py`
  - `src/gui/schema/classic/layout_table_selection.py`
  - `src/gui/schema/classic/layout_navigation.py`
- Convert `src/gui/schema/classic/layout.py` into a thin compatibility hub that re-exports:
  - `__init__`, `_build`, `_on_back_requested`, `_set_table_editor_enabled`,
    `_refresh_tables_list`, `_on_table_selected`, `_load_selected_table_into_editor`, `_browse_db_path`.
- Preserve context binding by importing the new `layout_*.py` modules in `src/gui/schema/classic_screen.py` and including them in `_bind_classic_module_context(...)`.
- Add contract coverage:
  - `tests/gui/test_classic_layout_method_contracts.py`
  - `tests/test_import_contracts.py` import checks for new modules.

## Consequences

- Classic layout logic is now concern-owned and easier to navigate without changing runtime behavior.
- `layout.py` becomes a thin compatibility surface while `SchemaProjectDesignerScreen` wrappers remain unchanged.
- `src/gui/schema/classic/layout.py` drops below the soft-budget threshold and no longer appears in module-size warnings.
