import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import RUN_CENTER_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiNotificationsIntegration(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _pump(self, cycles: int = 4) -> None:
        for _ in range(cycles):
            self.root.update_idletasks()
            self.root.update()

    def test_schema_generated_success_uses_notifications_not_info_dialog(self) -> None:
        self.app.show_screen(SCHEMA_V2_ROUTE)
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        table_name = "customers"
        rows = {table_name: [{f"{table_name}_id": 1}]}

        with mock.patch("src.gui_schema_core.messagebox.showinfo") as showinfo:
            screen._on_generated_ok(rows)

        self.assertEqual(showinfo.call_count, 0)
        history_messages = [entry.message for entry in screen.toast_center.history()]
        self.assertTrue(any("Generated" in message for message in history_messages))

    def test_schema_no_data_warning_uses_non_modal_notification(self) -> None:
        self.app.show_screen(SCHEMA_V2_ROUTE)
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        screen.generated_rows = {}

        warning_calls: list[tuple[str, str]] = []
        screen.error_surface.show_warning = lambda title, message: warning_calls.append((title, message))
        screen._on_export_csv()

        self.assertEqual(warning_calls, [])
        history_messages = [entry.message for entry in screen.toast_center.history()]
        self.assertTrue(any("Generate data first" in message for message in history_messages))

    def test_run_center_notifications_are_recorded_with_history(self) -> None:
        self.app.show_screen(RUN_CENTER_V2_ROUTE)
        screen = self.app.screens[RUN_CENTER_V2_ROUTE]
        screen._notify("Run Center notification test.", level="success")
        self._pump()

        history = screen.toast_center.history()
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[-1].message, "Run Center notification test.")
        self.assertEqual(history[-1].level, "success")


if __name__ == "__main__":
    unittest.main()
