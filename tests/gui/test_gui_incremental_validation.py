import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE

# Coverage handoff:
# - No test removals in this module.
# - Quality hardening only: debounce behavior is now asserted deterministically.


class TestGuiIncrementalValidation(unittest.TestCase):
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

    def _ensure_table_count(self, count: int) -> None:
        while len(self.screen.project.tables) < count:
            self.screen._add_table()
        self.assertGreaterEqual(len(self.screen.project.tables), count)

    def test_incremental_validation_is_debounced_for_table_scope(self) -> None:
        self._ensure_table_count(1)
        table_name = self.screen.project.tables[0].table_name
        callbacks: list[object] = []

        def _capture_after(_delay_ms: int, callback):
            callbacks.append(callback)
            return f"after-{len(callbacks)}"

        with mock.patch.object(
            self.screen,
            "_validate_project_detailed",
            wraps=self.screen._validate_project_detailed,
        ) as validate_project, mock.patch.object(
            self.screen,
            "after",
            side_effect=_capture_after,
        ):
            self.screen._stage_incremental_validation(table_names=(table_name,))
            self.screen._run_validation()
            self.screen._stage_incremental_validation(table_names=(table_name,))
            self.screen._run_validation()
            self.assertEqual(validate_project.call_count, 0)
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            self.assertEqual(validate_project.call_count, 1)

    def test_incremental_validation_uses_scoped_projection_tables(self) -> None:
        self._ensure_table_count(2)
        target_table = self.screen.project.tables[0].table_name
        seen_table_sets: list[list[str]] = []
        callbacks: list[object] = []
        original = self.screen._validate_project_detailed

        def _capture(project):
            seen_table_sets.append([table.table_name for table in project.tables])
            return original(project)

        def _capture_after(_delay_ms: int, callback):
            callbacks.append(callback)
            return f"after-{len(callbacks)}"

        with mock.patch.object(self.screen, "_validate_project_detailed", side_effect=_capture), mock.patch.object(
            self.screen,
            "after",
            side_effect=_capture_after,
        ):
            self.screen._stage_incremental_validation(table_names=(target_table,))
            self.screen._run_validation()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()

        self.assertIn(
            [target_table],
            seen_table_sets,
            "Incremental validation should run table-scoped validation projection for untouched schemas. "
            "Fix: keep scoped table projection for incremental table deltas.",
        )

    def test_generate_action_forces_full_validation_before_run(self) -> None:
        self._ensure_table_count(1)
        with mock.patch.object(
            self.screen,
            "_run_validation_full",
            wraps=self.screen._run_validation_full,
        ) as full_validation, mock.patch.object(self.screen.job_lifecycle, "run_async") as run_async:
            self.screen._on_generate_project()
            self.assertTrue(full_validation.called)
            self.assertTrue(run_async.called)

    def test_csv_export_forces_full_validation_before_run(self) -> None:
        self._ensure_table_count(1)
        table_name = self.screen.project.tables[0].table_name
        self.screen.generated_rows = {table_name: [{"id": 1}]}
        with mock.patch.object(
            self.screen,
            "_run_validation_full",
            wraps=self.screen._run_validation_full,
        ) as full_validation, mock.patch("src.gui_schema_core.filedialog.askdirectory", return_value=""):
            self.screen._on_export_csv()
            self.assertTrue(full_validation.called)


if __name__ == "__main__":
    unittest.main()
