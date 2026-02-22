import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.multiprocessing_runtime import PartitionPlanEntry, WorkerStatus
from src.performance_scaling import ChunkPlanEntry


class TestGuiP7LargeDataResponsiveness(unittest.TestCase):
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

    def _drain(self, *, rounds: int = 40) -> None:
        for _ in range(rounds):
            if not self.root.winfo_exists():
                return
            self.root.update_idletasks()
            self.root.update()

    def test_performance_workbench_bulk_setters_and_auto_paging(self):
        screen = self.app.screens["performance_workbench_v2"]
        estimates = [
            SimpleNamespace(
                table_name=f"table_{idx}",
                estimated_rows=idx,
                estimated_memory_mb=1.0,
                estimated_write_mb=2.0,
                estimated_seconds=3.0,
                risk_level="low",
                recommendation="ok",
            )
            for idx in range(1200)
        ]
        screen._populate_estimates(estimates)
        self._drain()
        self.assertTrue(screen.surface.diagnostics_table.view._pagination_enabled)
        self.assertEqual(len(screen.diagnostics_tree.get_children()), 200)

        entries = [
            ChunkPlanEntry(
                table_name=f"table_{idx}",
                stage=0,
                chunk_index=1,
                start_row=1,
                end_row=10,
                rows_in_chunk=10,
            )
            for idx in range(1200)
        ]
        screen._populate_chunk_plan(entries)
        self._drain()
        self.assertTrue(screen.surface.plan_table.view._pagination_enabled)
        self.assertEqual(len(screen.chunk_plan_tree.get_children()), 200)

    def test_execution_orchestrator_bulk_population_stays_paged(self):
        screen = self.app.screens["execution_orchestrator_v2"]
        partitions = [
            PartitionPlanEntry(
                partition_id=f"p_{idx}",
                table_name=f"table_{idx}",
                stage=0,
                chunk_index=1,
                start_row=1,
                end_row=10,
                rows_in_partition=10,
                assigned_worker=idx % 4,
                status="planned",
            )
            for idx in range(1200)
        ]
        screen._populate_partition_tree(partitions)
        self._drain()
        self.assertTrue(screen.surface.plan_table.view._pagination_enabled)
        self.assertEqual(len(screen.partition_tree.get_children()), 200)

        workers = {
            idx: WorkerStatus(
                worker_id=idx,
                current_table="table",
                current_partition_id=f"p_{idx}",
                rows_processed=idx,
                throughput_rows_per_sec=10.0,
                memory_mb=20.0,
                last_heartbeat_epoch=0.0,
                state="idle",
            )
            for idx in range(1200)
        }
        screen._populate_worker_tree(workers)
        self._drain()
        self.assertTrue(screen.surface.worker_table.view._pagination_enabled)
        self.assertEqual(len(screen.worker_tree.get_children()), 200)

    def test_run_center_refresh_paths_use_surface_bulk_setters(self):
        screen = self.app.screens["run_center_v2"]
        screen.project = object()

        estimate_payload = SimpleNamespace(
            estimates=[
                SimpleNamespace(
                    table_name="orders",
                    estimated_rows=10,
                    estimated_memory_mb=1.0,
                    estimated_write_mb=1.0,
                    estimated_seconds=1.0,
                    risk_level="low",
                    recommendation="ok",
                )
            ],
            summary=SimpleNamespace(total_rows=10, highest_risk="low"),
        )
        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
            "src.gui_v2_redesign.run_shared_estimate",
            return_value=estimate_payload,
        ), mock.patch.object(screen.surface, "set_diagnostics_rows") as set_diagnostics_rows:
            screen._run_estimate()
            set_diagnostics_rows.assert_called_once()

        plan_payload = [
            PartitionPlanEntry(
                partition_id="orders|stage=0|chunk=1",
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
        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
            "src.gui_v2_redesign.run_shared_build_partition_plan",
            return_value=plan_payload,
        ), mock.patch.object(screen.surface, "set_plan_rows") as set_plan_rows:
            screen._run_build_plan()
            set_plan_rows.assert_called_once()

        benchmark_result = SimpleNamespace(
            estimates=estimate_payload.estimates,
            chunk_plan=[
                SimpleNamespace(
                    table_name="orders",
                    stage=0,
                    chunk_index=1,
                    start_row=1,
                    end_row=10,
                )
            ],
            chunk_summary=SimpleNamespace(total_chunks=1, total_rows=10),
        )

        def _run_async_benchmark(**kwargs):
            kwargs["on_done"](benchmark_result)

        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch.object(
            screen.lifecycle,
            "run_async",
            side_effect=_run_async_benchmark,
        ), mock.patch.object(screen.surface, "set_diagnostics_rows") as set_diag_rows, mock.patch.object(
            screen.surface,
            "set_plan_rows",
        ) as set_plan_rows:
            screen._start_benchmark()
            set_diag_rows.assert_called_once()
            set_plan_rows.assert_called_once()

        generation_result = SimpleNamespace(
            partition_plan=plan_payload,
            failures=[SimpleNamespace(partition_id="orders|1", error="err", retry_count=0, action="retry")],
            strategy_result=SimpleNamespace(csv_paths={}, sqlite_counts={}),
            total_rows=10,
            fallback_used=False,
            mode="single_process",
        )

        def _run_async_generation(**kwargs):
            kwargs["on_done"](generation_result)

        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
            "src.gui_v2_redesign.build_profile_from_model",
            return_value=SimpleNamespace(output_mode="preview"),
        ), mock.patch.object(
            screen.lifecycle,
            "run_async",
            side_effect=_run_async_generation,
        ), mock.patch.object(screen.surface, "set_plan_rows") as set_plan_rows, mock.patch.object(
            screen.surface,
            "set_failures_rows",
        ) as set_failures_rows:
            screen._start_generation()
            set_plan_rows.assert_called_once()
            set_failures_rows.assert_called_once()

    def test_schema_preview_table_large_data_mode_stays_paged(self):
        screen = self.app.screens["schema_project_v2"]

        self.assertTrue(screen.preview_table._large_data_enabled)
        self.assertEqual(screen.preview_table._large_data_chunk_size, 150)

        screen.preview_table.set_columns(["id"])
        screen.preview_table.enable_pagination(page_size=100)
        screen.preview_table.set_rows([[idx] for idx in range(1200)])
        self._drain()

        self.assertTrue(screen.preview_table._pagination_enabled)
        self.assertEqual(len(screen.preview_tree.get_children()), screen.preview_table.page_size)


if __name__ == "__main__":
    unittest.main()


