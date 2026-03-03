import unittest

from src.gui.schema import classic_screen
from src.gui.schema.classic import actions_columns as classic_actions_columns
from src.gui.schema.classic_screen import SchemaProjectDesignerScreen


class TestClassicActionsColumnsMethodContracts(unittest.TestCase):
    def test_actions_columns_exports_expected_methods(self) -> None:
        expected = (
            "_refresh_columns_tree",
            "_selected_column_index",
            "_clear_column_editor",
            "_load_column_into_editor",
            "_on_column_dtype_changed",
            "_on_column_generator_changed",
            "_refresh_generator_options_for_dtype",
            "_on_pattern_entry_focus_out",
            "_on_pattern_preset_selected",
            "_sync_pattern_preset_from_pattern",
            "_apply_generator_params_template",
            "_open_table_correlation_groups_editor",
            "_on_table_correlation_groups_json_apply",
            "_on_column_selected",
            "_column_spec_from_editor",
            "_parse_column_name_csv",
            "_parse_optional_column_name",
            "_table_pk_name",
            "_int_columns",
            "_add_column",
            "_apply_selected_column_changes",
            "_remove_selected_column",
            "_move_selected_column",
        )
        for name in expected:
            self.assertTrue(hasattr(classic_actions_columns, name), f"Missing classic column action export: {name}")

    def test_classic_screen_wrappers_delegate_to_actions_columns_hub(self) -> None:
        wrapper_to_delegate = {
            "_refresh_columns_tree": classic_actions_columns._refresh_columns_tree,
            "_selected_column_index": classic_actions_columns._selected_column_index,
            "_clear_column_editor": classic_actions_columns._clear_column_editor,
            "_load_column_into_editor": classic_actions_columns._load_column_into_editor,
            "_on_column_dtype_changed": classic_actions_columns._on_column_dtype_changed,
            "_on_column_generator_changed": classic_actions_columns._on_column_generator_changed,
            "_refresh_generator_options_for_dtype": classic_actions_columns._refresh_generator_options_for_dtype,
            "_on_pattern_entry_focus_out": classic_actions_columns._on_pattern_entry_focus_out,
            "_on_pattern_preset_selected": classic_actions_columns._on_pattern_preset_selected,
            "_sync_pattern_preset_from_pattern": classic_actions_columns._sync_pattern_preset_from_pattern,
            "_apply_generator_params_template": classic_actions_columns._apply_generator_params_template,
            "_open_table_correlation_groups_editor": classic_actions_columns._open_table_correlation_groups_editor,
            "_on_table_correlation_groups_json_apply": classic_actions_columns._on_table_correlation_groups_json_apply,
            "_on_column_selected": classic_actions_columns._on_column_selected,
            "_column_spec_from_editor": classic_actions_columns._column_spec_from_editor,
            "_parse_column_name_csv": classic_actions_columns._parse_column_name_csv,
            "_parse_optional_column_name": classic_actions_columns._parse_optional_column_name,
            "_table_pk_name": classic_actions_columns._table_pk_name,
            "_int_columns": classic_actions_columns._int_columns,
            "_add_column": classic_actions_columns._add_column,
            "_apply_selected_column_changes": classic_actions_columns._apply_selected_column_changes,
            "_remove_selected_column": classic_actions_columns._remove_selected_column,
            "_move_selected_column": classic_actions_columns._move_selected_column,
        }
        for wrapper_name, delegate in wrapper_to_delegate.items():
            wrapper = SchemaProjectDesignerScreen.__dict__[wrapper_name]
            self.assertIn("classic_actions_columns", wrapper.__code__.co_names)
            self.assertIn(delegate.__name__, wrapper.__code__.co_names)

    def test_classic_screen_binds_new_actions_columns_modules_for_context(self) -> None:
        required_modules = (
            "classic_actions_columns_editor",
            "classic_actions_columns_spec",
            "classic_actions_columns_mutations",
        )
        for module_name in required_modules:
            self.assertTrue(
                hasattr(classic_screen, module_name),
                f"Missing bound classic actions_columns module import in classic_screen: {module_name}",
            )


if __name__ == "__main__":
    unittest.main()

