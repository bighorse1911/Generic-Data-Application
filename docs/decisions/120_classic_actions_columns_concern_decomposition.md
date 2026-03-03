# 120 - Classic Actions Columns Concern Decomposition

## Context

- `src/gui/schema/classic/actions_columns.py` remained a soft-budget hotspot at 701 LOC.
- `SchemaProjectDesignerScreen` in `src/gui/schema/classic_screen.py` depends on stable method wrapper names and module-context patch semantics.
- This slice required strict no-behavior-change parity for classic schema authoring flows.

## Decision

- Decompose classic column-action concerns into same-folder modules:
  - `src/gui/schema/classic/actions_columns_editor.py`
  - `src/gui/schema/classic/actions_columns_spec.py`
  - `src/gui/schema/classic/actions_columns_mutations.py`
- Convert `src/gui/schema/classic/actions_columns.py` into a thin compatibility hub that re-exports:
  - `_refresh_columns_tree`, `_selected_column_index`, `_clear_column_editor`, `_load_column_into_editor`,
    `_on_column_dtype_changed`, `_on_column_generator_changed`, `_refresh_generator_options_for_dtype`,
    `_on_pattern_entry_focus_out`, `_on_pattern_preset_selected`, `_sync_pattern_preset_from_pattern`,
    `_apply_generator_params_template`, `_open_table_correlation_groups_editor`,
    `_on_table_correlation_groups_json_apply`, `_on_column_selected`,
    `_column_spec_from_editor`, `_parse_column_name_csv`, `_parse_optional_column_name`,
    `_table_pk_name`, `_int_columns`, `_add_column`, `_apply_selected_column_changes`,
    `_remove_selected_column`, `_move_selected_column`.
- Preserve context binding by importing the new modules in `src/gui/schema/classic_screen.py` and including them in `_bind_classic_module_context(...)`.
- Add contract coverage:
  - `tests/gui/test_classic_actions_columns_method_contracts.py`
  - `tests/test_import_contracts.py` import checks for the new modules.

## Consequences

- Classic column-editor, parsing, and mutation logic is now concern-owned and easier to navigate.
- `actions_columns.py` is reduced to a thin compatibility surface while class wrappers remain unchanged.
- `src/gui/schema/classic/actions_columns.py` falls below the soft-budget threshold and no longer appears in module-size warnings.
