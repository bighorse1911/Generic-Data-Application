import unittest

from src.gui.schema import classic_screen
from src.gui.schema.classic import layout as classic_layout
from src.gui.schema.classic_screen import SchemaProjectDesignerScreen


class TestClassicLayoutMethodContracts(unittest.TestCase):
    def test_layout_exports_expected_methods(self) -> None:
        expected = (
            "__init__",
            "_build",
            "_on_back_requested",
            "_set_table_editor_enabled",
            "_refresh_tables_list",
            "_on_table_selected",
            "_load_selected_table_into_editor",
            "_browse_db_path",
        )
        for name in expected:
            self.assertTrue(hasattr(classic_layout, name), f"Missing classic layout export: {name}")

    def test_classic_screen_wrappers_delegate_to_classic_layout(self) -> None:
        wrapper_to_delegate = {
            "__init__": classic_layout.__init__,
            "_build": classic_layout._build,
            "_on_back_requested": classic_layout._on_back_requested,
            "_set_table_editor_enabled": classic_layout._set_table_editor_enabled,
            "_refresh_tables_list": classic_layout._refresh_tables_list,
            "_on_table_selected": classic_layout._on_table_selected,
            "_load_selected_table_into_editor": classic_layout._load_selected_table_into_editor,
            "_browse_db_path": classic_layout._browse_db_path,
        }
        for wrapper_name, delegate in wrapper_to_delegate.items():
            wrapper = SchemaProjectDesignerScreen.__dict__[wrapper_name]
            self.assertIn("classic_layout", wrapper.__code__.co_names)
            self.assertIn(delegate.__name__, wrapper.__code__.co_names)

    def test_classic_screen_binds_new_layout_modules_for_context(self) -> None:
        required_modules = (
            "classic_layout_init",
            "classic_layout_build",
            "classic_layout_table_selection",
            "classic_layout_navigation",
        )
        for module_name in required_modules:
            self.assertTrue(
                hasattr(classic_screen, module_name),
                f"Missing bound classic layout module import in classic_screen: {module_name}",
            )


if __name__ == "__main__":
    unittest.main()

