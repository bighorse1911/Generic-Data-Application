import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiSchemaDesignModes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._state_path = Path(self._tmp_dir.name) / "workspace_state.json"
        self._old_workspace_env = os.environ.get("GDA_WORKSPACE_STATE_PATH")
        os.environ["GDA_WORKSPACE_STATE_PATH"] = str(self._state_path)
        self._roots: list[tk.Tk] = []

    def tearDown(self) -> None:
        for root in self._roots:
            if root.winfo_exists():
                root.destroy()
        if self._old_workspace_env is None:
            os.environ.pop("GDA_WORKSPACE_STATE_PATH", None)
        else:
            os.environ["GDA_WORKSPACE_STATE_PATH"] = self._old_workspace_env
        self._tmp_dir.cleanup()

    def _build_schema_screen(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
        self._roots.append(root)
        root.withdraw()
        app = App(root, AppConfig())
        screen = app.screens[SCHEMA_V2_ROUTE]
        return root, screen

    @staticmethod
    def _mapped(widget) -> bool:
        return bool(widget.winfo_ismapped())

    def _expand_sections(self, screen) -> None:
        screen.project_panel.expand()
        screen.tables_panel.expand()
        screen.columns_panel.expand()
        screen.relationships_panel.expand()

    def test_default_mode_is_simple(self) -> None:
        root, screen = self._build_schema_screen()
        self._expand_sections(screen)
        root.update_idletasks()
        root.update()

        self.assertEqual(screen.schema_design_mode_var.get(), "simple")
        self.assertFalse(self._mapped(screen.project_complex_group))
        self.assertFalse(self._mapped(screen.table_mode_medium_group))
        self.assertFalse(self._mapped(screen.columns_mode_medium_group))
        self.assertFalse(self._mapped(screen.relationships_mode_medium_group))

    def test_mode_visibility_matrix(self) -> None:
        root, screen = self._build_schema_screen()
        self._expand_sections(screen)

        screen._set_schema_design_mode("medium", emit_feedback=False, persist=False)
        root.update_idletasks()
        root.update()
        self.assertFalse(self._mapped(screen.project_complex_group))
        self.assertTrue(self._mapped(screen.table_mode_medium_group))
        self.assertFalse(self._mapped(screen.table_mode_complex_group))
        self.assertTrue(self._mapped(screen.columns_mode_medium_group))
        self.assertTrue(self._mapped(screen.relationships_mode_medium_group))

        screen._set_schema_design_mode("complex", emit_feedback=False, persist=False)
        root.update_idletasks()
        root.update()
        self.assertTrue(self._mapped(screen.project_complex_group))
        self.assertTrue(self._mapped(screen.table_mode_medium_group))
        self.assertTrue(self._mapped(screen.table_mode_complex_group))
        self.assertTrue(self._mapped(screen.columns_mode_medium_group))
        self.assertTrue(self._mapped(screen.relationships_mode_medium_group))

    def test_downgrade_preserves_hidden_values_and_out_of_mode_generator(self) -> None:
        root, screen = self._build_schema_screen()
        self._expand_sections(screen)

        screen._set_schema_design_mode("complex", emit_feedback=False, persist=False)
        screen.project_timeline_constraints_var.set('[{"rule_id":"r1"}]')
        screen.col_dtype_var.set("text")
        screen.col_generator_var.set("state_transition")
        screen._refresh_generator_options_for_dtype()

        screen._set_schema_design_mode("simple", emit_feedback=True, persist=False)
        root.update_idletasks()
        root.update()

        self.assertEqual(screen.project_timeline_constraints_var.get(), '[{"rule_id":"r1"}]')
        self.assertEqual(screen.col_generator_var.get(), "state_transition")
        combo_values = tuple(screen.col_generator_combo.cget("values"))
        self.assertIn("state_transition", combo_values)
        self.assertIn("preserved", screen.status_var.get().lower())

    def test_workspace_state_restores_selected_mode(self) -> None:
        root_a, screen_a = self._build_schema_screen()
        self._expand_sections(screen_a)
        screen_a._set_schema_design_mode("medium", emit_feedback=False, persist=True)
        root_a.update_idletasks()
        root_a.update()
        self.assertTrue(self._state_path.exists())

        root_b, screen_b = self._build_schema_screen()
        self._expand_sections(screen_b)
        root_b.update_idletasks()
        root_b.update()
        self.assertEqual(screen_b.schema_design_mode_var.get(), "medium")
        self.assertTrue(self._mapped(screen_b.table_mode_medium_group))
        self.assertFalse(self._mapped(screen_b.project_complex_group))


if __name__ == "__main__":
    unittest.main()

