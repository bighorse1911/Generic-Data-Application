import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.multiprocessing_runtime import (
    MultiprocessRunCancelled,
    build_multiprocess_config,
    build_partition_plan,
    create_run_ledger,
    load_run_ledger,
    run_generation_with_multiprocessing,
    save_run_ledger,
    validate_run_ledger,
)
from src.performance_scaling import build_performance_profile
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


class TestMultiprocessingRuntime(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="mp_demo",
            seed=17,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=8,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_name", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    row_count=16,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("amount", "decimal", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="customer_id",
                    parent_table="customers",
                    parent_column="customer_id",
                    min_children=1,
                    max_children=2,
                )
            ],
        )

    def _profile(self):
        return build_performance_profile(
            target_tables_value="customers,orders",
            row_overrides_json_value="",
            preview_row_target_value="500",
            output_mode_value="preview",
            chunk_size_rows_value="5",
            preview_page_size_value="500",
            sqlite_batch_size_value="4000",
            csv_buffer_rows_value="4000",
            fk_cache_mode_value="auto",
            strict_deterministic_chunking_value=True,
        )

    def _multi_config(self):
        cpu_count = max(1, int(os.cpu_count() or 1))
        workers = min(2, cpu_count)
        return build_multiprocess_config(
            mode_value="multi_process_local",
            worker_count_value=str(workers),
            max_inflight_chunks_value=str(max(2, workers)),
            ipc_queue_size_value="64",
            retry_limit_value="1",
        )

    def test_build_multiprocess_config_parses_and_validates(self):
        config = self._multi_config()
        self.assertIn(config.mode, {"single_process", "multi_process_local"})
        self.assertGreaterEqual(config.worker_count, 1)
        self.assertGreaterEqual(config.max_inflight_chunks, config.worker_count)
        self.assertGreaterEqual(config.ipc_queue_size, config.max_inflight_chunks)

    def test_build_multiprocess_config_errors_are_actionable(self):
        with self.assertRaises(ValueError) as ctx:
            build_multiprocess_config(
                mode_value="single_process",
                worker_count_value="2",
                max_inflight_chunks_value="2",
                ipc_queue_size_value="4",
                retry_limit_value="1",
            )
        msg = str(ctx.exception)
        self.assertIn("Execution Orchestrator / Worker count", msg)
        self.assertIn("Fix:", msg)

    def test_build_partition_plan_is_deterministic(self):
        config = self._multi_config()
        first = build_partition_plan(self._project(), self._profile(), config)
        second = build_partition_plan(self._project(), self._profile(), config)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertEqual(first[0].stage, 0)
        self.assertEqual(first[-1].table_name, "orders")
        self.assertTrue(all(entry.assigned_worker >= 1 for entry in first))

    def test_run_generation_with_multiprocessing_single_process_mode(self):
        config = build_multiprocess_config(
            mode_value="single_process",
            worker_count_value="1",
            max_inflight_chunks_value="1",
            ipc_queue_size_value="1",
            retry_limit_value="0",
        )
        result = run_generation_with_multiprocessing(
            self._project(),
            self._profile(),
            config,
        )
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.mode, "single_process")
        self.assertGreater(result.total_rows, 0)
        self.assertTrue(result.strategy_result.rows_by_table)

    def test_run_generation_with_multiprocessing_multi_mode_emits_events(self):
        config = self._multi_config()
        seen_kinds: list[str] = []
        result = run_generation_with_multiprocessing(
            self._project(),
            self._profile(),
            config,
            on_event=lambda event: seen_kinds.append(event.kind),
        )
        self.assertIn("started", seen_kinds)
        self.assertIn("progress", seen_kinds)
        self.assertEqual(seen_kinds[-1], "run_done")
        self.assertFalse(result.fallback_used)
        self.assertGreater(result.total_rows, 0)

    def test_run_generation_with_multiprocessing_can_fallback(self):
        cpu_count = max(1, int(os.cpu_count() or 1))
        workers = min(2, cpu_count)
        config = build_multiprocess_config(
            mode_value="multi_process_local",
            worker_count_value=str(workers),
            max_inflight_chunks_value=str(max(2, workers)),
            ipc_queue_size_value="64",
            retry_limit_value="0",
        )
        plan = build_partition_plan(self._project(), self._profile(), config)
        self.assertTrue(plan)
        fail_partition_id = {plan[0].partition_id}

        result = run_generation_with_multiprocessing(
            self._project(),
            self._profile(),
            config,
            fallback_to_single_process=True,
            fail_partition_ids=fail_partition_id,
        )
        self.assertTrue(result.fallback_used)
        self.assertTrue(result.failures)
        self.assertGreater(result.total_rows, 0)

    def test_run_ledger_roundtrip_and_metadata_validation(self):
        config = self._multi_config()
        plan = build_partition_plan(self._project(), self._profile(), config)
        ledger = create_run_ledger(self._project(), self._profile(), config, plan)

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_ledger.json"
            saved_path = save_run_ledger(str(path), ledger)
            loaded = load_run_ledger(str(saved_path))
            self.assertEqual(loaded["project_name"], "mp_demo")
            validate_run_ledger(self._project(), self._profile(), config, loaded)

            bad = dict(loaded)
            bad["project_name"] = "other_project"
            with self.assertRaises(ValueError) as ctx:
                validate_run_ledger(self._project(), self._profile(), config, bad)
            msg = str(ctx.exception)
            self.assertIn("Execution Orchestrator / Run recovery", msg)
            self.assertIn("Fix:", msg)

    def test_run_generation_with_multiprocessing_cancel_is_actionable(self):
        config = build_multiprocess_config(
            mode_value="single_process",
            worker_count_value="1",
            max_inflight_chunks_value="1",
            ipc_queue_size_value="1",
            retry_limit_value="0",
        )
        with self.assertRaises(MultiprocessRunCancelled) as ctx:
            run_generation_with_multiprocessing(
                self._project(),
                self._profile(),
                config,
                cancel_requested=lambda: True,
            )
        msg = str(ctx.exception)
        self.assertIn("Execution Orchestrator / Cancel", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
