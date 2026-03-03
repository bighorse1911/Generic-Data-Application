import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiP19OnboardingEmptyStates(unittest.TestCase):
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

    def test_initial_empty_state_exposes_first_run_shortcuts(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        self.assertTrue(hasattr(screen, "create_starter_schema_btn"))
        self.assertTrue(hasattr(screen, "load_starter_fixture_btn"))
        self.assertIn("no schema tables yet", screen.onboarding_project_hint_var.get().lower())
        self.assertIn("no schema", screen.generate_empty_hint_var.get().lower())

    def test_create_starter_schema_enables_generate_preview_path(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        screen._create_starter_schema()
        self.assertGreaterEqual(len(screen.project.tables), 2)
        self.assertIn("schema ready", screen.onboarding_project_hint_var.get().lower())

        first_table = screen.project.tables[0]
        sample_row: dict[str, object] = {}
        for column in first_table.columns:
            if column.dtype == "int":
                sample_row[column.name] = 1
            elif column.dtype == "decimal":
                sample_row[column.name] = 1.25
            elif column.dtype == "datetime":
                sample_row[column.name] = "2025-01-01T00:00:00Z"
            else:
                sample_row[column.name] = "value"

        rows = {first_table.table_name: [sample_row]}

        def _run_async(*, worker, on_done, on_failed, phase_label, success_phase=None, failure_phase=None):
            del worker, on_failed, phase_label, success_phase, failure_phase
            on_done(rows)
            return True

        with mock.patch.object(screen.job_lifecycle, "run_async", side_effect=_run_async):
            screen._on_generate_sample()

        self.assertTrue(bool(screen.generated_rows))
        self.assertEqual(screen.preview_table_var.get(), first_table.table_name)
        self.assertIn("preview", screen.generate_empty_hint_var.get().lower())

    def test_load_starter_fixture_shortcut_loads_fixture_project(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        screen._load_starter_fixture_shortcut()
        self.assertGreater(len(screen.project.tables), 0)
        self.assertIn("starter fixture loaded", screen.status_var.get().lower())


if __name__ == "__main__":
    unittest.main()
