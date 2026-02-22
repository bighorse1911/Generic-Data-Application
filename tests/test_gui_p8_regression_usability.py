import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.multiprocessing_runtime import MultiprocessEvent


class TestGuiP8RegressionUsability(unittest.TestCase):
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

    def _drain(self, *, rounds: int = 10) -> None:
        for _ in range(rounds):
            if not self.root.winfo_exists():
                return
            self.root.update_idletasks()
            self.root.update()

    def _history_statuses(self, run_center) -> list[str]:
        statuses: list[str] = []
        for item in run_center.history_tree.get_children():
            values = run_center.history_tree.item(item, "values")
            if len(values) > 1:
                statuses.append(str(values[1]))
        return statuses

    def test_v2_route_transition_sequence_tracks_current_screen(self):
        route_sequence = [
            "home_v2",
            "schema_studio_v2",
            "schema_project_v2",
            "run_center_v2",
            "performance_workbench_v2",
            "execution_orchestrator_v2",
            "erd_designer_v2",
            "location_selector_v2",
            "generation_behaviors_guide_v2",
        ]
        for route in route_sequence:
            with self.subTest(route=route):
                self.app.show_screen(route)
                self.assertEqual(self.app.current_screen_name, route)

    def test_schema_studio_section_selection_updates_viewmodel_nav_and_status(self):
        self.app.show_screen("schema_studio_v2")
        studio = self.app.screens["schema_studio_v2"]

        studio.select_section("tables")
        self.assertEqual(studio.view_model.selected_section, "tables")
        self.assertEqual(studio.shell.active_nav_key, "tables")
        self.assertIn("tables section", studio.shell.status_var.get().lower())

        studio.select_section("run")
        self.assertEqual(studio.view_model.selected_section, "run")
        self.assertEqual(studio.shell.active_nav_key, "run")
        self.assertIn("run section", studio.shell.status_var.get().lower())

    def test_schema_studio_dirty_navigation_block_and_allow(self):
        self.app.show_screen("schema_studio_v2")
        studio = self.app.screens["schema_studio_v2"]
        schema_v2 = self.app.screens[SCHEMA_V2_ROUTE]
        schema_v2.mark_dirty("test")  # type: ignore[attr-defined]

        with mock.patch.object(schema_v2, "confirm_discard_or_save", return_value=False):
            studio._navigate_with_guard("run_center_v2", "opening Run Center")
            self.assertEqual(self.app.current_screen_name, "schema_studio_v2")
            self.assertIn("navigation cancelled", studio.shell.status_var.get().lower())

        with mock.patch.object(schema_v2, "confirm_discard_or_save", return_value=True):
            studio._navigate_with_guard("run_center_v2", "opening Run Center")
            self.assertEqual(self.app.current_screen_name, "run_center_v2")

    def test_schema_studio_guard_error_sets_retryable_status(self):
        self.app.show_screen("schema_studio_v2")
        studio = self.app.screens["schema_studio_v2"]
        schema_v2 = self.app.screens[SCHEMA_V2_ROUTE]
        schema_v2.mark_dirty("test")  # type: ignore[attr-defined]

        with mock.patch.object(schema_v2, "confirm_discard_or_save", side_effect=RuntimeError("boom")):
            studio._navigate_with_guard("run_center_v2", "opening Run Center")

        self.assertEqual(self.app.current_screen_name, "schema_studio_v2")
        self.assertIn("unable to confirm schema changes", studio.shell.status_var.get().lower())

    def test_legacy_bridge_and_demo_routes_are_absent(self):
        retired = [
            "home",
            "schema_project",
            "schema_project_kit",
            "schema_project_legacy",
            "generation_behaviors_guide",
            "erd_designer",
            "location_selector",
            "performance_workbench",
            "execution_orchestrator",
            "schema_demo_v2",
            "erd_designer_v2_bridge",
            "location_selector_v2_bridge",
            "generation_behaviors_guide_v2_bridge",
        ]
        for route in retired:
            with self.subTest(route=route):
                with self.assertRaises(KeyError):
                    self.app.show_screen(route)

    def test_run_center_shortcuts_toggle_on_route_switch(self):
        run_center = self.app.screens["run_center_v2"]
        self.assertFalse(run_center.shortcut_manager.is_active)

        self.app.show_screen("run_center_v2")
        self.assertTrue(run_center.shortcut_manager.is_active)

        self.app.show_screen("schema_studio_v2")
        self.assertFalse(run_center.shortcut_manager.is_active)

        self.app.show_screen("run_center_v2")
        self.assertTrue(run_center.shortcut_manager.is_active)

    def test_run_center_cancel_if_running_invokes_cancel_only_while_running(self):
        run_center = self.app.screens["run_center_v2"]
        with mock.patch.object(run_center, "_cancel_run") as cancel_run:
            run_center.lifecycle.state.is_running = False
            run_center._cancel_if_running()
            cancel_run.assert_not_called()

            run_center.lifecycle.state.is_running = True
            run_center._cancel_if_running()
            cancel_run.assert_called_once()
            run_center.lifecycle.state.is_running = False

    def test_start_generation_fallback_sets_phase_label_and_forwards_flag(self):
        run_center = self.app.screens["run_center_v2"]
        run_center.project = object()
        captured: dict[str, object] = {}

        def _run_async(**kwargs):
            captured["phase_label"] = kwargs["phase_label"]
            kwargs["worker"]()
            return True

        def _run_generation(*_args, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace()

        with mock.patch.object(run_center, "_ensure_project", return_value=True), mock.patch(
            "src.gui_v2_redesign.build_profile_from_model",
            return_value=SimpleNamespace(output_mode="preview"),
        ), mock.patch(
            "src.gui_v2_redesign.run_generation_multiprocess",
            side_effect=_run_generation,
        ), mock.patch.object(
            run_center.lifecycle,
            "run_async",
            side_effect=_run_async,
        ):
            run_center._start_generation(fallback_to_single_process=True)

        self.assertEqual(captured["phase_label"], "Running with fallback...")
        self.assertTrue(captured["fallback_to_single_process"])

    def test_start_generation_cancelled_by_missing_output_path_does_not_run_async(self):
        run_center = self.app.screens["run_center_v2"]
        run_center.project = object()

        with mock.patch.object(run_center, "_ensure_project", return_value=True), mock.patch(
            "src.gui_v2_redesign.build_profile_from_model",
            return_value=SimpleNamespace(output_mode="csv"),
        ), mock.patch(
            "src.gui_v2_redesign.filedialog.askdirectory",
            return_value="",
        ), mock.patch.object(run_center.lifecycle, "run_async") as run_async:
            run_center._start_generation()
            run_async.assert_not_called()
            self.assertIn("Run cancelled (no CSV output folder selected).", run_center.shell.status_var.get())

        with mock.patch.object(run_center, "_ensure_project", return_value=True), mock.patch(
            "src.gui_v2_redesign.build_profile_from_model",
            return_value=SimpleNamespace(output_mode="sqlite"),
        ), mock.patch(
            "src.gui_v2_redesign.filedialog.asksaveasfilename",
            return_value="",
        ), mock.patch.object(run_center.lifecycle, "run_async") as run_async:
            run_center._start_generation()
            run_async.assert_not_called()
            self.assertIn("Run cancelled (no SQLite output path selected).", run_center.shell.status_var.get())

    def test_run_center_partition_failed_event_updates_failures_and_lifecycle_state(self):
        run_center = self.app.screens["run_center_v2"]
        run_center.surface.clear_tree(run_center.failures_tree)
        run_center.lifecycle.set_running(True, "Running")

        run_center._on_multiprocess_event(
            MultiprocessEvent(kind="fallback", message="Switching to fallback", retry_count=1)
        )
        run_center._on_multiprocess_event(
            MultiprocessEvent(
                kind="partition_failed",
                partition_id="orders|1",
                message="failure",
                retry_count=2,
            )
        )
        self._drain()

        self.assertTrue(run_center.lifecycle.state.fallback_used)
        self.assertEqual(run_center.lifecycle.state.last_retry_count, 2)
        self.assertEqual(len(run_center.failures_tree.get_children()), 1)
        values = run_center.failures_tree.item(run_center.failures_tree.get_children()[0], "values")
        self.assertEqual(values[0], "orders|1")
        self.assertEqual(values[1], "failure")
        self.assertEqual(values[2], "2")
        run_center.lifecycle.set_running(False, "Idle")

    def test_run_center_cancelled_and_failed_handlers_update_state_and_history(self):
        run_center = self.app.screens["run_center_v2"]
        run_center.surface.clear_tree(run_center.history_tree)
        run_center.lifecycle.set_running(True, "Running")
        run_center._on_run_cancelled("cancelled by user")
        self._drain()

        self.assertFalse(run_center.lifecycle.state.is_running)
        self.assertEqual(run_center.live_phase_var.get(), "Run cancelled.")
        self.assertEqual(run_center.live_eta_var.get(), "ETA: cancelled")
        statuses = self._history_statuses(run_center)
        self.assertIn("cancelled", statuses)

        run_center.surface.clear_tree(run_center.history_tree)
        run_center.lifecycle.set_running(True, "Running")
        with mock.patch.object(run_center.error_surface, "emit_formatted") as emit_formatted:
            run_center._on_run_failed("boom")
            emit_formatted.assert_called_once_with("boom", mode="mixed")
        self._drain()

        self.assertFalse(run_center.lifecycle.state.is_running)
        self.assertEqual(run_center.live_phase_var.get(), "Failed")
        statuses = self._history_statuses(run_center)
        self.assertIn("failed", statuses)


if __name__ == "__main__":
    unittest.main()


