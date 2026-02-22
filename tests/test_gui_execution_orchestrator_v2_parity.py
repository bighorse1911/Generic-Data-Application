from types import SimpleNamespace
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import PartitionPlanEntry
from src.multiprocessing_runtime import WorkerStatus


class TestGuiExecutionOrchestratorV2Parity(unittest.TestCase):
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

    def _routes(self) -> tuple[str, str]:
        return ("execution_orchestrator_v2", ORCHESTRATOR_V2_ROUTE)

    def test_build_plan_uses_bulk_plan_and_worker_setters(self) -> None:
        plan = [
            PartitionPlanEntry(
                partition_id="orders|1",
                table_name="orders",
                stage=0,
                chunk_index=1,
                start_row=1,
                end_row=10,
                rows_in_partition=10,
                assigned_worker=0,
                status="planned",
            )
        ]
        workers = {
            0: WorkerStatus(
                worker_id=0,
                current_table="orders",
                current_partition_id="orders|1",
                rows_processed=0,
                throughput_rows_per_sec=0.0,
                memory_mb=0.0,
                last_heartbeat_epoch=0.0,
                state="idle",
            )
        }
        for route in self._routes():
            with self.subTest(route=route):
                screen = self.app.screens[route]
                screen.project = object()
                with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
                    "src.gui_execution_orchestrator_base.run_build_partition_plan",
                    return_value=plan,
                ), mock.patch(
                    "src.gui_execution_orchestrator_base.build_config_from_model",
                    return_value=SimpleNamespace(),
                ), mock.patch(
                    "src.gui_execution_orchestrator_base.build_worker_status_snapshot",
                    return_value=workers,
                ), mock.patch.object(screen.surface, "set_plan_rows") as set_plan, mock.patch.object(
                    screen.surface,
                    "set_worker_rows",
                ) as set_workers:
                    screen._build_plan()
                    set_plan.assert_called_once()
                    set_workers.assert_called_once()

    def test_start_run_and_start_fallback_use_expected_phase_labels(self) -> None:
        result = SimpleNamespace(
            partition_plan=[],
            worker_status={},
            failures=[],
            strategy_result=SimpleNamespace(csv_paths={}, sqlite_counts={}),
            total_rows=0,
            fallback_used=False,
        )
        labels: list[str] = []

        def _run_async(**kwargs):
            labels.append(kwargs["phase_label"])
            kwargs["on_done"](result)
            return True

        for route in self._routes():
            with self.subTest(route=route):
                screen = self.app.screens[route]
                screen.project = object()
                labels.clear()
                with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
                    "src.gui_execution_orchestrator_base.build_profile_from_model",
                    return_value=SimpleNamespace(output_mode="preview"),
                ), mock.patch(
                    "src.gui_execution_orchestrator_base.build_config_from_model",
                    return_value=SimpleNamespace(),
                ), mock.patch.object(
                    screen.lifecycle,
                    "run_async",
                    side_effect=_run_async,
                ):
                    screen._start_run()
                    screen._start_run(fallback_to_single_process=True)
                self.assertEqual(labels, ["Running...", "Running with fallback..."])

    def test_cancel_and_config_save_load_paths(self) -> None:
        for route in self._routes():
            with self.subTest(route=route):
                screen = self.app.screens[route]
                screen.lifecycle.set_running(True, "Running")
                screen._cancel_run()
                self.assertTrue(screen.lifecycle.state.cancel_requested)
                screen.lifecycle.set_running(False, "Idle")

                with tempfile.TemporaryDirectory() as tmp_dir:
                    config_path = f"{tmp_dir}/orchestrator_config.json"
                    with mock.patch(
                        "src.gui_execution_orchestrator_base.execution_run_config_payload",
                        return_value={"execution_mode": "single_process"},
                    ), mock.patch(
                        "src.gui_execution_orchestrator_base.filedialog.asksaveasfilename",
                        return_value=config_path,
                    ):
                        screen._save_run_config()
                    self.assertTrue(screen.surface.status_var.get().startswith("Saved run config"))

                    with mock.patch(
                        "src.gui_execution_orchestrator_base.filedialog.askopenfilename",
                        return_value=config_path,
                    ), mock.patch("src.gui_execution_orchestrator_base.apply_execution_run_config_payload"), mock.patch(
                        "src.gui_execution_orchestrator_base.build_profile_from_model",
                        return_value=SimpleNamespace(output_mode="preview"),
                    ), mock.patch(
                        "src.gui_execution_orchestrator_base.build_config_from_model",
                        return_value=SimpleNamespace(),
                    ):
                        screen._load_run_config()
                    self.assertTrue(screen.surface.status_var.get().startswith("Loaded run config"))

    def test_partition_failed_event_updates_failures_table(self) -> None:
        for route in self._routes():
            with self.subTest(route=route):
                screen = self.app.screens[route]
                screen.surface.clear_tree(screen.failures_tree)
                screen._on_runtime_event(
                    MultiprocessEvent(
                        kind="partition_failed",
                        partition_id="orders|1",
                        message="failed",
                        retry_count=1,
                    )
                )
                self.assertEqual(len(screen.failures_tree.get_children()), 1)


if __name__ == "__main__":
    unittest.main()


