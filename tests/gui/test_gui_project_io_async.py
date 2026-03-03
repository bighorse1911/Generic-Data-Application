import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiProjectIoAsync(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())
        self.screen = self.app.screens[SCHEMA_V2_ROUTE]

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _immediate_run_async(self, **kwargs) -> bool:
        payload = kwargs["worker"]()
        kwargs["on_done"](payload)
        return True

    def test_async_save_uses_project_io_lifecycle_and_marks_clean(self) -> None:
        self.screen._add_table()
        self.assertTrue(self.screen.is_dirty)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "project_async_save.json")
            with mock.patch(
                "src.gui_schema_editor_base.filedialog.asksaveasfilename",
                return_value=path,
            ), mock.patch.object(
                self.screen.project_io_lifecycle,
                "run_async",
                side_effect=self._immediate_run_async,
            ) as run_async:
                started = self.screen._start_save_project_async()

        self.assertTrue(started)
        self.assertTrue(run_async.called)
        self.assertFalse(self.screen.is_dirty)
        self.assertIn("Saved project:", self.screen.status_var.get())

    def test_async_load_uses_project_io_lifecycle_and_applies_loaded_project(self) -> None:
        self.screen.project_name_var.set("loaded_project_name")
        self.screen._add_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "project_async_load.json")
            with mock.patch(
                "src.gui_schema_core.filedialog.asksaveasfilename",
                return_value=path,
            ):
                self.assertTrue(self.screen._save_project())

            self.screen.project_name_var.set("modified_name")
            self.assertTrue(self.screen.is_dirty)

            with mock.patch.object(
                self.screen,
                "confirm_discard_or_save",
                return_value=True,
            ), mock.patch(
                "src.gui_schema_editor_base.filedialog.askopenfilename",
                return_value=path,
            ), mock.patch.object(
                self.screen.project_io_lifecycle,
                "run_async",
                side_effect=self._immediate_run_async,
            ) as run_async:
                self.screen._start_load_project_async()

        self.assertTrue(run_async.called)
        self.assertEqual(self.screen.project_name_var.get(), "loaded_project_name")
        self.assertFalse(self.screen.is_dirty)
        self.assertIn("Loaded project:", self.screen.status_var.get())

    def test_cancelled_save_and_load_do_not_start_async_jobs(self) -> None:
        self.screen._add_table()
        with mock.patch(
            "src.gui_schema_editor_base.filedialog.asksaveasfilename",
            return_value="",
        ), mock.patch.object(self.screen.project_io_lifecycle, "run_async") as run_async:
            started = self.screen._start_save_project_async()
        self.assertFalse(started)
        run_async.assert_not_called()
        self.assertIn("cancelled", self.screen.status_var.get().lower())

        with mock.patch.object(
            self.screen,
            "confirm_discard_or_save",
            return_value=True,
        ), mock.patch(
            "src.gui_schema_editor_base.filedialog.askopenfilename",
            return_value="",
        ), mock.patch.object(self.screen.project_io_lifecycle, "run_async") as run_async:
            self.screen._start_load_project_async()
        run_async.assert_not_called()
        self.assertIn("cancelled", self.screen.status_var.get().lower())

    def test_project_io_guard_blocks_duplicate_start_requests(self) -> None:
        self.screen.project_io_lifecycle.state.is_running = True
        with mock.patch.object(self.screen.project_io_lifecycle, "run_async") as run_async:
            started = self.screen._start_save_project_async()
        self.screen.project_io_lifecycle.state.is_running = False
        self.assertFalse(started)
        run_async.assert_not_called()
        self.assertIn("already running", self.screen.status_var.get())


if __name__ == "__main__":
    unittest.main()
