import unittest

import src.gui_v2_schema_project as schema_v2_module
from src.gui_v2_schema_project import SchemaProjectV2Screen


class TestGuiV2SchemaProjectMethodContracts(unittest.TestCase):
    def test_extracted_modules_export_expected_methods(self) -> None:
        layout_expected = (
            "build_columns_panel",
            "build_header",
            "_on_back_requested",
        )
        form_expected = (
            "_attach_generator_form_sync",
            "_find_column_editor_box",
            "_install_generator_form_host",
            "_set_generator_form_message",
            "_current_table_column_names",
            "_visible_generator_specs",
            "_visible_advanced_specs",
            "_clear_dynamic_form_rows",
            "_rebuild_generator_form_fields",
            "_build_field_binding",
            "_browse_generator_path",
            "_open_structured_object_editor",
            "_on_generator_form_field_changed",
            "_on_params_json_var_changed",
            "_parse_params_json_object",
            "_sync_generator_form_from_params_json",
            "_collect_structured_params",
            "_dependency_source_values",
            "_ensure_depends_on_contains",
            "_sync_params_json_from_generator_form",
            "_reload_generator_form_from_json",
            "_reset_generator_form_to_template",
            "_set_generator_form_enabled",
            "_apply_generator_form_mode_visibility",
            "_apply_schema_design_mode_overrides",
        )
        for name in layout_expected:
            self.assertTrue(
                hasattr(schema_v2_module.v2_schema_layout, name),
                f"Missing extracted layout method: {name}",
            )
        for name in form_expected:
            self.assertTrue(
                hasattr(schema_v2_module.v2_schema_form, name),
                f"Missing extracted form method: {name}",
            )

    def test_screen_wrappers_delegate_to_extracted_modules(self) -> None:
        wrapper_to_module = {
            "build_columns_panel": "v2_schema_layout",
            "build_header": "v2_schema_layout",
            "_on_back_requested": "v2_schema_layout",
            "_attach_generator_form_sync": "v2_schema_form",
            "_rebuild_generator_form_fields": "v2_schema_form",
            "_sync_params_json_from_generator_form": "v2_schema_form",
            "_apply_generator_form_mode_visibility": "v2_schema_form",
        }
        for wrapper_name, module_name in wrapper_to_module.items():
            wrapper = SchemaProjectV2Screen.__dict__[wrapper_name]
            self.assertIn(
                module_name,
                wrapper.__code__.co_names,
                f"Wrapper '{wrapper_name}' should delegate via {module_name}",
            )

    def test_new_modules_are_imported_on_facade_module(self) -> None:
        self.assertTrue(hasattr(schema_v2_module, "v2_schema_layout"))
        self.assertTrue(hasattr(schema_v2_module, "v2_schema_form"))


if __name__ == "__main__":
    unittest.main()

