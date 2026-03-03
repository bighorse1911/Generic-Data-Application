import unittest

from src.gui_tools import erd_designer_view
from src.gui_tools.erd_designer_view import ERDDesignerToolFrame


class TestErdDesignerViewMethodContracts(unittest.TestCase):
    def test_tool_frame_exposes_legacy_method_surface(self) -> None:
        expected_methods = (
            "__init__",
            "_erd_error",
            "_show_error_dialog",
            "_browse_schema_path",
            "_toggle_authoring_panel",
            "_set_combo_values",
            "_table_names",
            "_table_for_name",
            "_columns_for_table",
            "_sync_authoring_controls_from_project",
            "_on_column_pk_changed",
            "_on_column_table_changed",
            "_on_edit_table_selected",
            "_on_edit_column_table_changed",
            "_on_edit_column_selected",
            "_on_edit_column_pk_changed",
            "_reset_table_editor",
            "_reset_column_editor",
            "_save_table_shared",
            "_save_column_shared",
            "_on_relationship_child_table_changed",
            "_on_relationship_parent_table_changed",
            "_create_new_schema",
            "_add_table",
            "_edit_table",
            "_add_column",
            "_edit_column",
            "_add_relationship",
            "_load_and_render",
            "_export_schema_json",
            "_export_erd",
            "_on_options_changed",
            "_draw_erd",
            "_table_name_at_canvas_point",
            "_on_erd_drag_start",
            "_on_erd_drag_motion",
            "_on_erd_drag_end",
        )
        for method_name in expected_methods:
            self.assertTrue(
                hasattr(ERDDesignerToolFrame, method_name),
                f"Missing ERDDesignerToolFrame method contract: {method_name}",
            )

    def test_wrappers_delegate_to_concern_modules(self) -> None:
        wrapper_to_module_alias = {
            "__init__": "erd_build",
            "_erd_error": "erd_helpers",
            "_show_error_dialog": "erd_helpers",
            "_browse_schema_path": "erd_io_export",
            "_toggle_authoring_panel": "erd_authoring_sync",
            "_set_combo_values": "erd_helpers",
            "_table_names": "erd_helpers",
            "_table_for_name": "erd_helpers",
            "_columns_for_table": "erd_helpers",
            "_sync_authoring_controls_from_project": "erd_authoring_sync",
            "_on_column_pk_changed": "erd_authoring_sync",
            "_on_column_table_changed": "erd_authoring_sync",
            "_on_edit_table_selected": "erd_authoring_sync",
            "_on_edit_column_table_changed": "erd_authoring_sync",
            "_on_edit_column_selected": "erd_authoring_sync",
            "_on_edit_column_pk_changed": "erd_authoring_sync",
            "_reset_table_editor": "erd_authoring_sync",
            "_reset_column_editor": "erd_authoring_sync",
            "_save_table_shared": "erd_authoring_sync",
            "_save_column_shared": "erd_authoring_sync",
            "_on_relationship_child_table_changed": "erd_authoring_sync",
            "_on_relationship_parent_table_changed": "erd_authoring_sync",
            "_create_new_schema": "erd_authoring_actions",
            "_add_table": "erd_authoring_actions",
            "_edit_table": "erd_authoring_actions",
            "_add_column": "erd_authoring_actions",
            "_edit_column": "erd_authoring_actions",
            "_add_relationship": "erd_authoring_actions",
            "_load_and_render": "erd_io_export",
            "_export_schema_json": "erd_io_export",
            "_export_erd": "erd_io_export",
            "_on_options_changed": "erd_rendering",
            "_draw_erd": "erd_rendering",
            "_table_name_at_canvas_point": "erd_dragging",
            "_on_erd_drag_start": "erd_dragging",
            "_on_erd_drag_motion": "erd_dragging",
            "_on_erd_drag_end": "erd_dragging",
        }
        for wrapper_name, module_alias in wrapper_to_module_alias.items():
            wrapper = ERDDesignerToolFrame.__dict__[wrapper_name]
            self.assertIn(module_alias, wrapper.__code__.co_names)
            self.assertIn(wrapper_name, wrapper.__code__.co_names)

    def test_concern_modules_are_imported_and_bound(self) -> None:
        required_module_aliases = (
            "erd_build",
            "erd_helpers",
            "erd_authoring_sync",
            "erd_authoring_actions",
            "erd_io_export",
            "erd_rendering",
            "erd_dragging",
        )
        for alias in required_module_aliases:
            self.assertTrue(
                hasattr(erd_designer_view, alias),
                f"Missing module alias on erd_designer_view facade: {alias}",
            )


if __name__ == "__main__":
    unittest.main()
