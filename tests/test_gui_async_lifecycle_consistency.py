import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App


class TestGUIAsyncLifecycleConsistency(unittest.TestCase):
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

    def test_schema_kit_uses_shared_job_lifecycle_controller(self):
        screen = self.app.screens["schema_project"]
        self.assertTrue(hasattr(screen, "job_lifecycle"))
        self.assertFalse(screen.job_lifecycle.state.is_running)

    def test_legacy_schema_post_ui_callback_is_teardown_safe(self):
        screen = self.app.screens["schema_project_legacy"]
        calls: list[str] = []
        with mock.patch.object(screen, "_ui_alive", return_value=True), mock.patch.object(
            screen,
            "after",
            side_effect=tk.TclError("widget destroyed"),
        ):
            screen._post_ui_callback(lambda: calls.append("called"))

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
