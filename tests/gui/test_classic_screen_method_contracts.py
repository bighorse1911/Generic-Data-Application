import unittest

from src.gui_schema_core import SchemaProjectDesignerScreen


class TestClassicScreenMethodContracts(unittest.TestCase):
    def test_patch_critical_methods_exist(self) -> None:
        required_methods = (
            "_set_running",
            "_refresh_tables_list",
            "_set_table_editor_enabled",
            "_add_table",
            "_remove_table",
            "_apply_table_changes",
            "_apply_generator_params_template",
            "_add_column",
            "_apply_selected_column_changes",
            "_remove_selected_column",
            "_move_selected_column",
            "_add_fk",
            "_remove_selected_fk",
            "_on_generated_ok",
            "_clear_generated",
            "_on_export_csv",
            "_on_sqlite_ok",
            "_save_project",
            "_load_project",
        )
        for method_name in required_methods:
            self.assertTrue(
                hasattr(SchemaProjectDesignerScreen, method_name),
                f"Missing SchemaProjectDesignerScreen method contract: {method_name}",
            )


if __name__ == "__main__":
    unittest.main()
