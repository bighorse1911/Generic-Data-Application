import unittest

from src.gui.schema import editor_base
from src.gui.schema.editor import layout as editor_layout
from src.gui.schema.editor_base import SchemaEditorBaseScreen


class TestEditorLayoutMethodContracts(unittest.TestCase):
    def test_layout_exports_expected_methods(self) -> None:
        expected = (
            "_build",
            "on_show",
            "on_hide",
            "build_header",
            "_current_schema_design_mode",
            "_set_schema_design_mode",
            "_on_schema_design_mode_changed",
            "_mode_allowed_generators_for_dtype",
            "_set_grid_group_visible",
            "_project_has_advanced_values",
            "_table_has_medium_values",
            "_table_has_complex_values",
            "_project_has_out_of_mode_generators",
            "_collect_hidden_mode_value_labels",
            "_apply_schema_design_mode_ui",
            "build_project_panel",
            "build_tables_panel",
            "build_columns_panel",
            "build_relationships_panel",
            "build_generate_panel",
            "build_status_bar",
            "_on_back_requested",
            "_on_main_tab_changed",
            "_register_shortcuts",
            "_register_focus_anchors",
            "_on_screen_destroy",
            "_refresh_onboarding_hints",
        )
        for name in expected:
            self.assertTrue(hasattr(editor_layout, name), f"Missing layout export: {name}")

    def test_editor_base_wrappers_point_to_layout_delegates(self) -> None:
        wrapper_to_delegate = {
            "_build": editor_layout._build,
            "on_show": editor_layout.on_show,
            "on_hide": editor_layout.on_hide,
            "build_header": editor_layout.build_header,
            "_current_schema_design_mode": editor_layout._current_schema_design_mode,
            "_set_schema_design_mode": editor_layout._set_schema_design_mode,
            "_on_schema_design_mode_changed": editor_layout._on_schema_design_mode_changed,
            "_mode_allowed_generators_for_dtype": editor_layout._mode_allowed_generators_for_dtype,
            "_project_has_advanced_values": editor_layout._project_has_advanced_values,
            "_project_has_out_of_mode_generators": editor_layout._project_has_out_of_mode_generators,
            "_collect_hidden_mode_value_labels": editor_layout._collect_hidden_mode_value_labels,
            "_apply_schema_design_mode_ui": editor_layout._apply_schema_design_mode_ui,
            "build_project_panel": editor_layout.build_project_panel,
            "build_tables_panel": editor_layout.build_tables_panel,
            "build_columns_panel": editor_layout.build_columns_panel,
            "build_relationships_panel": editor_layout.build_relationships_panel,
            "build_generate_panel": editor_layout.build_generate_panel,
            "build_status_bar": editor_layout.build_status_bar,
            "_on_back_requested": editor_layout._on_back_requested,
            "_on_main_tab_changed": editor_layout._on_main_tab_changed,
            "_register_shortcuts": editor_layout._register_shortcuts,
            "_register_focus_anchors": editor_layout._register_focus_anchors,
            "_on_screen_destroy": editor_layout._on_screen_destroy,
            "_refresh_onboarding_hints": editor_layout._refresh_onboarding_hints,
        }
        for wrapper_name, delegate in wrapper_to_delegate.items():
            wrapper = SchemaEditorBaseScreen.__dict__[wrapper_name]
            self.assertIn("editor_layout", wrapper.__code__.co_names)
            self.assertIn(delegate.__name__, wrapper.__code__.co_names)

    def test_new_layout_modules_are_bound_for_context(self) -> None:
        required_modules = (
            "editor_layout_build",
            "editor_layout_modes",
            "editor_layout_panels",
            "editor_layout_panels_project",
            "editor_layout_panels_tables",
            "editor_layout_panels_columns",
            "editor_layout_panels_relationships",
            "editor_layout_panels_generate",
            "editor_layout_navigation",
            "editor_layout_shortcuts",
            "editor_layout_onboarding",
        )
        for module_name in required_modules:
            self.assertTrue(
                hasattr(editor_base, module_name),
                f"Missing bound layout module import in editor_base: {module_name}",
            )


if __name__ == "__main__":
    unittest.main()
