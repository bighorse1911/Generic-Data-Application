import unittest

from src.gui_v2.commands import build_profile_from_viewmodel
from src.gui_v2.commands import run_build_partition_plan
from src.gui_v2.commands import run_estimate
from src.gui_v2.commands import run_generation
from src.gui_v2.navigation import DirtyRouteGuard
from src.gui_v2.navigation import guarded_navigation
from src.gui_v2.viewmodels import RunCenterViewModel
from src.gui_v2.viewmodels import coerce_execution_mode
from src.gui_v2.viewmodels import coerce_output_mode
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


class _DirtyScreen:
    def __init__(self, *, is_dirty: bool, allow: bool):
        self.is_dirty = is_dirty
        self._allow = allow

    def confirm_discard_or_save(self, *, action_name: str):
        return self._allow and action_name != ""


class TestGuiV2FeatureC(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="v2_feature_c",
            seed=11,
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

    def _viewmodel(self) -> RunCenterViewModel:
        model = RunCenterViewModel()
        model.output_mode = "preview"
        model.execution_mode = "single_process"
        model.worker_count = "1"
        model.max_inflight_chunks = "1"
        model.ipc_queue_size = "1"
        model.retry_limit = "0"
        model.target_tables = "customers,orders"
        model.row_overrides_json = ""
        model.chunk_size_rows = "5"
        model.preview_row_target = "500"
        model.preview_page_size = "500"
        model.sqlite_batch_size = "5000"
        model.csv_buffer_rows = "5000"
        model.fk_cache_mode = "auto"
        model.strict_deterministic_chunking = True
        return model

    def test_dirty_route_guard_allows_clean_or_non_guarded(self):
        guard = DirtyRouteGuard()
        self.assertTrue(guard.can_navigate(dirty_screen=None, action_name="x").allowed)
        screen = object()
        self.assertTrue(guard.can_navigate(dirty_screen=screen, action_name="x").allowed)

    def test_dirty_route_guard_blocks_when_user_cancels(self):
        guard = DirtyRouteGuard()
        dirty_screen = _DirtyScreen(is_dirty=True, allow=False)
        result = guard.can_navigate(dirty_screen=dirty_screen, action_name="leave")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "user_cancelled")

    def test_guarded_navigation_runs_only_when_allowed(self):
        guard = DirtyRouteGuard()
        state = {"called": False}

        result = guarded_navigation(
            guard=guard,
            dirty_screen=_DirtyScreen(is_dirty=True, allow=True),
            action_name="go",
            navigate=lambda: state.__setitem__("called", True),
        )
        self.assertTrue(result.allowed)
        self.assertTrue(state["called"])

    def test_viewmodel_mode_coercion(self):
        self.assertEqual(coerce_output_mode("CSV"), "csv")
        self.assertEqual(coerce_output_mode("bad"), "preview")
        self.assertEqual(coerce_execution_mode("MULTI_PROCESS_LOCAL"), "multi_process_local")
        self.assertEqual(coerce_execution_mode("bad"), "single_process")

    def test_commands_estimate_and_partition_plan(self):
        project = self._project()
        model = self._viewmodel()

        diagnostics = run_estimate(project, model)
        self.assertGreaterEqual(diagnostics.summary.total_rows, 1)
        self.assertTrue(diagnostics.estimates)

        plan = run_build_partition_plan(project, model)
        self.assertTrue(plan)
        self.assertEqual(plan[0].stage, 0)

    def test_commands_generation_preview_single_process(self):
        result = run_generation(self._project(), self._viewmodel())
        self.assertEqual(result.mode, "single_process")
        self.assertGreater(result.total_rows, 0)
        self.assertFalse(result.fallback_used)

    def test_profile_build_errors_remain_actionable(self):
        model = self._viewmodel()
        model.output_mode = "parquet"
        with self.assertRaises(ValueError) as ctx:
            build_profile_from_viewmodel(model)
        message = str(ctx.exception)
        self.assertIn("Performance Workbench / Output mode", message)
        self.assertIn("Fix:", message)


if __name__ == "__main__":
    unittest.main()

