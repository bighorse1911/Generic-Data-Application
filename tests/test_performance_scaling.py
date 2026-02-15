import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.performance_scaling import (
    PerformanceRunCancelled,
    build_chunk_plan,
    build_performance_profile,
    estimate_workload,
    run_generation_with_strategy,
    run_performance_benchmark,
    summarize_chunk_plan,
    summarize_estimates,
    validate_performance_profile,
)
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


class TestPerformanceScaling(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="perf_demo",
            seed=9,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=10,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_name", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    row_count=30,
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
                    max_children=4,
                )
            ],
        )

    def _profile_kwargs(self) -> dict[str, object]:
        return {
            "target_tables_value": "customers, orders",
            "row_overrides_json_value": "{\"orders\": 40}",
            "preview_row_target_value": "500",
            "output_mode_value": "preview",
            "chunk_size_rows_value": "1000",
            "preview_page_size_value": "500",
            "sqlite_batch_size_value": "4000",
            "csv_buffer_rows_value": "4000",
            "fk_cache_mode_value": "auto",
            "strict_deterministic_chunking_value": True,
        }

    def test_build_performance_profile_parses_inputs(self):
        profile = build_performance_profile(**self._profile_kwargs())
        self.assertEqual(profile.target_tables, ("customers", "orders"))
        self.assertEqual(profile.row_overrides, {"orders": 40})
        self.assertEqual(profile.preview_row_target, 500)
        self.assertEqual(profile.output_mode, "preview")
        self.assertEqual(profile.chunk_size_rows, 1000)
        self.assertEqual(profile.preview_page_size, 500)

    def test_build_profile_errors_are_actionable(self):
        with self.assertRaises(ValueError) as mode_ctx:
            build_performance_profile(
                **{
                    **self._profile_kwargs(),
                    "output_mode_value": "parquet",
                }
            )
        mode_msg = str(mode_ctx.exception)
        self.assertIn("Performance Workbench / Output mode", mode_msg)
        self.assertIn("Fix:", mode_msg)

        with self.assertRaises(ValueError) as json_ctx:
            build_performance_profile(
                **{
                    **self._profile_kwargs(),
                    "row_overrides_json_value": "{\"orders\":",
                }
            )
        json_msg = str(json_ctx.exception)
        self.assertIn("Performance Workbench / Row overrides JSON", json_msg)
        self.assertIn("line", json_msg)
        self.assertIn("column", json_msg)
        self.assertIn("Fix:", json_msg)

    def test_validate_profile_rejects_unknown_target_table(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "target_tables_value": "customers,missing_table",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            validate_performance_profile(self._project(), profile)
        msg = str(ctx.exception)
        self.assertIn("Performance Workbench / Target tables", msg)
        self.assertIn("unknown table selection", msg)
        self.assertIn("Fix:", msg)

    def test_validate_profile_rejects_fk_minimum_violation(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "row_overrides_json_value": "{\"customers\": 25, \"orders\": 20}",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            validate_performance_profile(self._project(), profile)
        msg = str(ctx.exception)
        self.assertIn("Performance Workbench / Row overrides / orders", msg)
        self.assertIn("requires at least", msg)
        self.assertIn("Fix:", msg)

    def test_validate_profile_requires_strict_deterministic_chunking(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "strict_deterministic_chunking_value": False,
            }
        )
        with self.assertRaises(ValueError) as ctx:
            validate_performance_profile(self._project(), profile)
        msg = str(ctx.exception)
        self.assertIn("Performance Workbench / Strict deterministic chunking", msg)
        self.assertIn("Fix:", msg)

    def test_estimate_workload_is_deterministic_and_summarized(self):
        profile = build_performance_profile(**self._profile_kwargs())
        validate_performance_profile(self._project(), profile)

        first = estimate_workload(self._project(), profile)
        second = estimate_workload(self._project(), profile)
        self.assertEqual(first, second)
        self.assertEqual([e.table_name for e in first], ["customers", "orders"])

        summary = summarize_estimates(first)
        self.assertEqual(summary.total_rows, 50)
        self.assertGreaterEqual(summary.total_memory_mb, 0.0)
        self.assertGreaterEqual(summary.total_write_mb, 0.0)
        self.assertGreaterEqual(summary.total_seconds, 0.0)
        self.assertIn(summary.highest_risk, {"low", "medium", "high"})

    def test_build_chunk_plan_is_deterministic_and_fk_staged(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "chunk_size_rows_value": "8",
            }
        )
        validate_performance_profile(self._project(), profile)

        first = build_chunk_plan(self._project(), profile)
        second = build_chunk_plan(self._project(), profile)
        self.assertEqual(first, second)
        self.assertTrue(first)

        stage_by_table = {entry.table_name: entry.stage for entry in first}
        self.assertEqual(stage_by_table["customers"], 0)
        self.assertEqual(stage_by_table["orders"], 1)

        customer_chunks = [entry for entry in first if entry.table_name == "customers"]
        self.assertEqual(len(customer_chunks), 2)
        self.assertEqual((customer_chunks[0].start_row, customer_chunks[0].end_row), (1, 8))
        self.assertEqual((customer_chunks[1].start_row, customer_chunks[1].end_row), (9, 10))

        order_chunks = [entry for entry in first if entry.table_name == "orders"]
        self.assertEqual(len(order_chunks), 5)
        self.assertEqual((order_chunks[0].start_row, order_chunks[0].end_row), (1, 8))
        self.assertEqual((order_chunks[-1].start_row, order_chunks[-1].end_row), (33, 40))

        summary = summarize_chunk_plan(first)
        self.assertEqual(summary.table_count, 2)
        self.assertEqual(summary.total_chunks, 7)
        self.assertEqual(summary.total_rows, 50)
        self.assertEqual(summary.max_stage, 1)

    def test_build_chunk_plan_rejects_cyclic_dependencies(self):
        cycle_project = SchemaProject(
            name="cycle",
            seed=1,
            tables=[
                TableSpec(
                    table_name="a",
                    row_count=5,
                    columns=[
                        ColumnSpec("a_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("b_id", "int", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="b",
                    row_count=5,
                    columns=[
                        ColumnSpec("b_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("a_id", "int", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("a", "b_id", "b", "b_id", 1, 3),
                ForeignKeySpec("b", "a_id", "a", "a_id", 1, 3),
            ],
        )
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "target_tables_value": "a, b",
                "row_overrides_json_value": "",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            build_chunk_plan(cycle_project, profile)
        msg = str(ctx.exception)
        self.assertIn("Performance Workbench / Chunk plan", msg)
        self.assertIn("cyclic table dependencies", msg)
        self.assertIn("Fix:", msg)

    def test_run_performance_benchmark_emits_events(self):
        profile = build_performance_profile(**self._profile_kwargs())
        seen_kinds: list[str] = []

        result = run_performance_benchmark(
            self._project(),
            profile,
            on_event=lambda event: seen_kinds.append(event.kind),
        )
        self.assertTrue(result.chunk_plan)
        self.assertIn("started", seen_kinds)
        self.assertIn("progress", seen_kinds)
        self.assertEqual(seen_kinds[-1], "run_done")

    def test_run_performance_benchmark_cancellation_is_actionable(self):
        profile = build_performance_profile(**self._profile_kwargs())

        with self.assertRaises(PerformanceRunCancelled) as ctx:
            run_performance_benchmark(
                self._project(),
                profile,
                cancel_requested=lambda: True,
            )
        msg = str(ctx.exception)
        self.assertIn("Performance Workbench / Cancel", msg)
        self.assertIn("Fix:", msg)

    def test_run_generation_with_strategy_preview_mode(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "output_mode_value": "preview",
            }
        )
        result = run_generation_with_strategy(self._project(), profile)
        self.assertEqual(result.csv_paths, {})
        self.assertEqual(result.sqlite_counts, {})
        self.assertGreater(result.total_rows, 0)
        self.assertIn("customers", result.rows_by_table)
        self.assertIn("orders", result.rows_by_table)

    def test_run_generation_with_strategy_csv_mode_writes_files(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "output_mode_value": "csv",
                "csv_buffer_rows_value": "2",
            }
        )
        with TemporaryDirectory() as tmp:
            result = run_generation_with_strategy(
                self._project(),
                profile,
                output_csv_folder=tmp,
            )
            self.assertTrue(result.csv_paths)
            for table, path in result.csv_paths.items():
                self.assertTrue(Path(path).exists(), f"Expected CSV output for table '{table}'.")

    def test_run_generation_with_strategy_sqlite_mode_writes_rows(self):
        profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "output_mode_value": "sqlite",
            }
        )
        with TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "perf_strategy.db")
            result = run_generation_with_strategy(
                self._project(),
                profile,
                output_sqlite_path=db_path,
            )
            self.assertTrue(Path(db_path).exists())
            self.assertTrue(result.sqlite_counts)
            self.assertGreater(sum(result.sqlite_counts.values()), 0)

    def test_run_generation_with_strategy_requires_output_paths(self):
        csv_profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "output_mode_value": "csv",
            }
        )
        with self.assertRaises(ValueError) as csv_ctx:
            run_generation_with_strategy(self._project(), csv_profile)
        self.assertIn("Performance Workbench / Run", str(csv_ctx.exception))
        self.assertIn("Fix:", str(csv_ctx.exception))

        sqlite_profile = build_performance_profile(
            **{
                **self._profile_kwargs(),
                "output_mode_value": "sqlite",
            }
        )
        with self.assertRaises(ValueError) as sqlite_ctx:
            run_generation_with_strategy(self._project(), sqlite_profile)
        self.assertIn("Performance Workbench / Run", str(sqlite_ctx.exception))
        self.assertIn("Fix:", str(sqlite_ctx.exception))


if __name__ == "__main__":
    unittest.main()
