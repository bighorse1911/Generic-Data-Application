import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_PRIMARY_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestSchemaRouteConsolidation(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self):
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _collect_button_text(self, widget: tk.Widget) -> list[str]:
        texts: list[str] = []
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button):
                texts.append(str(child.cget("text")))
            texts.extend(self._collect_button_text(child))
        return texts

    def test_home_hides_schema_fallback_buttons(self):
        home = self.app.screens["home"]
        button_text = "\n".join(self._collect_button_text(home))
        self.assertIn("Schema Project Designer (Production)", button_text)
        self.assertNotIn("Schema Project Designer (Kit Preview)", button_text)
        self.assertNotIn("Schema Project Designer (Legacy Fallback)", button_text)

    def test_schema_routes_share_primary_instance(self):
        self.assertIs(self.app.screens["schema_project"], self.app.screens["schema_project_kit"])

    def test_schema_studio_tabs_navigate_to_schema_project_v2_route(self):
        studio = self.app.screens["schema_studio_v2"]
        captured_targets: list[str] = []

        def _capture(target_route: str, _action_name: str) -> None:
            captured_targets.append(target_route)

        studio._navigate_with_guard = _capture  # type: ignore[attr-defined]

        for key in ("project", "tables", "columns", "relationships"):
            frame = studio._tab_by_name[key]  # type: ignore[attr-defined]
            buttons = [child for child in frame.winfo_children() if isinstance(child, ttk.Button)]
            self.assertEqual(len(buttons), 1)
            buttons[0].invoke()

        self.assertEqual(
            captured_targets,
            [SCHEMA_V2_ROUTE, SCHEMA_V2_ROUTE, SCHEMA_V2_ROUTE, SCHEMA_V2_ROUTE],
        )

    def test_fallback_routes_remain_registered_and_callable(self):
        self.app.show_screen("schema_project_kit")
        self.app.show_screen("schema_project_legacy")

        legacy = self.app.screens["schema_project_legacy"]
        self.assertIn("deprecated", legacy.status_var.get().lower())  # type: ignore[attr-defined]
        self.assertIn("schema_project", legacy.status_var.get())  # type: ignore[attr-defined]

    def test_schema_studio_guard_prefers_v2_dirty_state_then_fallback_primary(self):
        self.app.show_screen("schema_studio_v2")
        studio = self.app.screens["schema_studio_v2"]
        schema_v2 = self.app.screens[SCHEMA_V2_ROUTE]
        primary = self.app.screens[SCHEMA_PRIMARY_ROUTE]
        schema_v2.mark_dirty("test")  # type: ignore[attr-defined]
        primary.mark_clean()  # type: ignore[attr-defined]

        with mock.patch.object(schema_v2, "confirm_discard_or_save", return_value=False) as blocked, mock.patch.object(
            primary,
            "confirm_discard_or_save",
            return_value=True,
        ) as primary_unused:
            studio._navigate_with_guard("run_center_v2", "opening Run Center")
            blocked.assert_called_once()
            primary_unused.assert_not_called()
            self.assertEqual(self.app.current_screen_name, "schema_studio_v2")
            self.assertIn("Navigation cancelled", studio.shell.status_var.get())

        with mock.patch.object(schema_v2, "confirm_discard_or_save", return_value=True) as allowed:
            studio._navigate_with_guard("run_center_v2", "opening Run Center")
            allowed.assert_called_once()
            self.assertEqual(self.app.current_screen_name, "run_center_v2")

        schema_v2.mark_clean()  # type: ignore[attr-defined]
        primary.mark_dirty("test")  # type: ignore[attr-defined]
        self.app.show_screen("schema_studio_v2")
        with mock.patch.object(primary, "confirm_discard_or_save", return_value=False) as primary_blocked:
            studio._navigate_with_guard("run_center_v2", "opening Run Center")
            primary_blocked.assert_called_once()
            self.assertEqual(self.app.current_screen_name, "schema_studio_v2")


if __name__ == "__main__":
    unittest.main()
