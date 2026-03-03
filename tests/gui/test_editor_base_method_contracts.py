import unittest

from src.gui.schema.editor_base import SchemaEditorBaseScreen


class TestEditorBaseMethodContracts(unittest.TestCase):
    def test_patch_critical_methods_exist(self) -> None:
        required_methods = (
            "_run_validation",
            "_save_project",
            "_load_project",
            "_add_table",
            "_add_column",
            "_add_fk",
            "_on_generate_project",
            "_on_export_csv",
            "_on_create_insert_sqlite",
            "_on_generate_sample",
        )
        for method_name in required_methods:
            self.assertTrue(
                hasattr(SchemaEditorBaseScreen, method_name),
                f"Missing SchemaEditorBaseScreen method contract: {method_name}",
            )


if __name__ == "__main__":
    unittest.main()
