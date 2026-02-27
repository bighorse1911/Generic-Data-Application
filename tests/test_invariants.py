import os
import tempfile
import tkinter as tk
import unittest
from datetime import date

from src.config import AppConfig
from src.generator_project import generate_project_rows
from src.gui_home import App
from src.gui_home import GENERATION_BEHAVIOR_GUIDE
from src.gui_route_policy import ERD_V2_ROUTE
from src.gui_route_policy import GENERATION_GUIDE_V2_ROUTE
from src.gui_route_policy import HOME_V2_ROUTE
from src.gui_route_policy import LOCATION_V2_ROUTE
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_route_policy import RUN_CENTER_V2_ROUTE
from src.gui_route_policy import SCHEMA_STUDIO_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.gui_v2_execution_orchestrator import ExecutionOrchestratorV2Screen
from src.gui_v2_performance_workbench import PerformanceWorkbenchV2Screen
from src.gui_v2_redesign import ERDDesignerV2Screen
from src.gui_v2_redesign import GenerationBehaviorsGuideV2Screen
from src.gui_v2_redesign import HomeV2Screen
from src.gui_v2_redesign import LocationSelectorV2Screen
from src.gui_v2_redesign import RunCenterV2Screen
from src.gui_v2_redesign import SchemaStudioV2Screen
from src.gui_v2_schema_project import SchemaProjectV2Screen
from src.gui_schema_shared import (
    DTYPES,
    EXPORT_OPTION_CSV,
    EXPORT_OPTION_SQLITE,
    GENERATORS,
    validate_export_option,
)
from src.schema_project_io import load_project_from_json
from src.schema_project_io import save_project_to_json
from src.schema_project_model import ColumnSpec
from src.schema_project_model import ForeignKeySpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project
from src.storage_sqlite_project import create_tables
from src.storage_sqlite_project import insert_project_rows


class TestInvariants(unittest.TestCase):
    def _project(self, seed: int = 42) -> SchemaProject:
        return SchemaProject(
            name="invariants",
            seed=seed,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=8,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("name", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("status", "text", nullable=False, choices=["NEW", "PAID", "SHIPPED"]),
                    ],
                ),
                TableSpec(
                    table_name="order_items",
                    columns=[
                        ColumnSpec("order_item_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("order_id", "int", nullable=False),
                        ColumnSpec("sku", "text", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("orders", "customer_id", "customers", "customer_id", 1, 3),
                ForeignKeySpec("order_items", "order_id", "orders", "order_id", 1, 4),
            ],
        )

    def test_seed_is_deterministic_for_same_project(self):
        project = self._project(seed=77)
        a = generate_project_rows(project)
        b = generate_project_rows(project)
        self.assertEqual(a, b)

    def test_different_seed_changes_output(self):
        a = generate_project_rows(self._project(seed=77))
        b = generate_project_rows(self._project(seed=78))
        self.assertNotEqual(a, b)

    def test_primary_keys_never_null_and_unique(self):
        project = self._project(seed=13)
        rows = generate_project_rows(project)

        for table in project.tables:
            pk_col = [c.name for c in table.columns if c.primary_key][0]
            values = [r.get(pk_col) for r in rows[table.table_name]]
            self.assertTrue(all(v is not None for v in values))
            self.assertEqual(len(values), len(set(values)))

    def test_foreign_keys_always_exist_in_parent(self):
        project = self._project(seed=21)
        rows = generate_project_rows(project)

        for fk in project.foreign_keys:
            parent_values = {r[fk.parent_column] for r in rows[fk.parent_table]}
            for child_row in rows[fk.child_table]:
                child_val = child_row[fk.child_column]
                self.assertIn(child_val, parent_values)

    def test_single_fk_cardinality_bounds_hold_per_parent(self):
        project = self._project(seed=31)
        rows = generate_project_rows(project)

        incoming_counts: dict[str, int] = {}
        for fk in project.foreign_keys:
            incoming_counts[fk.child_table] = incoming_counts.get(fk.child_table, 0) + 1

        for fk in project.foreign_keys:
            if incoming_counts.get(fk.child_table, 0) != 1:
                continue
            counts_by_parent: dict[int, int] = {
                int(r[fk.parent_column]): 0 for r in rows[fk.parent_table]
            }
            for child_row in rows[fk.child_table]:
                pid = int(child_row[fk.child_column])
                counts_by_parent[pid] = counts_by_parent.get(pid, 0) + 1

            for count in counts_by_parent.values():
                self.assertGreaterEqual(count, fk.min_children)
                self.assertLessEqual(count, fk.max_children)

    def test_dg03_timeline_constraints_are_deterministic_and_enforced(self):
        project = SchemaProject(
            name="invariants_dg03",
            seed=333,
            tables=[
                TableSpec(
                    table_name="signup",
                    row_count=4,
                    columns=[
                        ColumnSpec("signup_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "signup_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-01", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("signup_id", "int", nullable=False),
                        ColumnSpec(
                            "ordered_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-12-01", "end": "2025-03-01"},
                        ),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("orders", "signup_id", "signup", "signup_id", 1, 1),
            ],
            timeline_constraints=[
                {
                    "rule_id": "signup_to_order",
                    "child_table": "orders",
                    "child_column": "ordered_date",
                    "references": [
                        {
                            "parent_table": "signup",
                            "parent_column": "signup_date",
                            "via_child_fk": "signup_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 3,
                        }
                    ],
                }
            ],
        )
        first = generate_project_rows(project)
        second = generate_project_rows(project)
        self.assertEqual(first, second)

        signup_by_id = {int(row["signup_id"]): row for row in first["signup"]}
        for row in first["orders"]:
            parent = signup_by_id[int(row["signup_id"])]
            delta = (
                date.fromisoformat(str(row["ordered_date"]))
                - date.fromisoformat(str(parent["signup_date"]))
            ).days
            self.assertGreaterEqual(delta, 0)
            self.assertLessEqual(delta, 3)

    def test_dg06_profiles_are_deterministic_and_applied(self):
        project = SchemaProject(
            name="invariants_dg06",
            seed=334,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=12,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "segment",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["VIP", "STD"], "weights": [1.0, 1.0]},
                        ),
                        ColumnSpec(
                            "note",
                            "text",
                            nullable=True,
                            generator="choice_weighted",
                            params={"choices": ["ok", "ok2"], "weights": [1.0, 1.0]},
                        ),
                        ColumnSpec(
                            "amount",
                            "decimal",
                            nullable=False,
                            generator="uniform_float",
                            params={"min": 10.0, "max": 10.0},
                        ),
                    ],
                ),
            ],
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "mar_note",
                    "table": "events",
                    "column": "note",
                    "kind": "missingness",
                    "mechanism": "mar",
                    "base_rate": 0.3,
                    "driver_column": "segment",
                    "value_weights": {"VIP": 2.0, "STD": 0.2},
                    "default_weight": 0.2,
                },
                {
                    "profile_id": "drift_amount",
                    "table": "events",
                    "column": "amount",
                    "kind": "quality_issue",
                    "issue_type": "drift",
                    "rate": 1.0,
                    "step": 1.0,
                    "start_index": 1,
                },
            ],
        )
        first = generate_project_rows(project)
        second = generate_project_rows(project)
        self.assertEqual(first, second)

        event_rows = first["events"]
        self.assertTrue(any(row["note"] is None for row in event_rows))
        self.assertEqual([float(row["amount"]) for row in event_rows], [11.0 + idx for idx in range(len(event_rows))])

    def test_json_roundtrip_preserves_project(self):
        project = self._project(seed=9)

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_json_loader_accepts_legacy_defaults(self):
        legacy_project = {
            "name": "legacy_project",
            "tables": [
                {
                    "table_name": "customers",
                    "columns": [
                        {"name": "customer_id", "dtype": "int", "nullable": False, "primary_key": True},
                        {"name": "name", "dtype": "text", "nullable": False},
                    ],
                },
                {
                    "table_name": "orders",
                    "columns": [
                        {"name": "order_id", "dtype": "int", "nullable": False, "primary_key": True},
                        {"name": "customer_id", "dtype": "int", "nullable": False},
                    ],
                },
            ],
            "foreign_keys": [
                {
                    "child_table": "orders",
                    "child_column": "customer_id",
                    "parent_table": "customers",
                    "parent_column": "customer_id",
                }
            ],
        }

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            import json

            with open(path, "w", encoding="utf-8") as f:
                json.dump(legacy_project, f)
            loaded = load_project_from_json(path)
            self.assertEqual(loaded.seed, 12345)
            self.assertEqual(loaded.tables[0].row_count, 100)
            self.assertIsNone(loaded.tables[0].business_key_unique_count)
            self.assertEqual(loaded.foreign_keys[0].min_children, 1)
            self.assertEqual(loaded.foreign_keys[0].max_children, 3)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_sqlite_insert_counts_match_generated_rows(self):
        project = self._project(seed=11)
        rows = generate_project_rows(project)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()
        try:
            create_tables(db_path, project)
            inserted = insert_project_rows(db_path, project, rows, chunk_size=500)
            expected = {table_name: len(table_rows) for table_name, table_rows in rows.items()}
            self.assertEqual(inserted, expected)
        finally:
            try:
                os.remove(db_path)
            except PermissionError:
                pass

    def test_validation_errors_include_location_and_hint(self):
        bad = SchemaProject(
            name="bad",
            seed=1,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("score", "float", nullable=False, min_value=10, max_value=2),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'people'", msg)
        self.assertIn("column 'score'", msg)
        self.assertIn("Fix:", msg)

    def test_runtime_generator_error_includes_location_issue_and_fix(self):
        bad = SchemaProject(
            name="bad_runtime_generator",
            seed=1,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("value", "text", nullable=False, generator="not_registered"),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            generate_project_rows(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'people', column 'value'", msg)
        self.assertIn("Fix:", msg)

    def test_export_option_validation_accepts_supported_values(self):
        self.assertEqual(validate_export_option(EXPORT_OPTION_CSV), EXPORT_OPTION_CSV)
        self.assertEqual(validate_export_option(f"  {EXPORT_OPTION_SQLITE}  "), EXPORT_OPTION_SQLITE)

    def test_export_option_validation_error_has_location_and_hint(self):
        with self.assertRaises(ValueError) as ctx:
            validate_export_option("Parquet")
        msg = str(ctx.exception)
        self.assertIn("Generate / Preview / Export / SQLite panel", msg)
        self.assertIn("Fix: choose one of", msg)

    def test_direction3_gui_lists_decimal_and_semantic_numeric_generators(self):
        self.assertIn("decimal", DTYPES)
        self.assertIn("bytes", DTYPES)
        self.assertNotIn("float", DTYPES)
        self.assertIn("money", GENERATORS)
        self.assertIn("percent", GENERATORS)
        self.assertIn("if_then", GENERATORS)
        self.assertIn("derived_expr", GENERATORS)
        self.assertIn("time_offset", GENERATORS)
        self.assertIn("hierarchical_category", GENERATORS)
        self.assertIn("ordered_choice", GENERATORS)
        self.assertIn("state_transition", GENERATORS)

    def test_gui_navigation_contract_v2_only(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return

        root.withdraw()
        try:
            app = App(root, AppConfig())
            expected_routes = {
                HOME_V2_ROUTE,
                SCHEMA_STUDIO_V2_ROUTE,
                SCHEMA_V2_ROUTE,
                RUN_CENTER_V2_ROUTE,
                PERFORMANCE_V2_ROUTE,
                ORCHESTRATOR_V2_ROUTE,
                ERD_V2_ROUTE,
                LOCATION_V2_ROUTE,
                GENERATION_GUIDE_V2_ROUTE,
            }
            self.assertEqual(set(app.screens.keys()), expected_routes)
            self.assertEqual(app.current_screen_name, HOME_V2_ROUTE)

            self.assertIsInstance(app.screens[HOME_V2_ROUTE], HomeV2Screen)
            self.assertIsInstance(app.screens[SCHEMA_STUDIO_V2_ROUTE], SchemaStudioV2Screen)
            self.assertIsInstance(app.screens[SCHEMA_V2_ROUTE], SchemaProjectV2Screen)
            self.assertIsInstance(app.screens[RUN_CENTER_V2_ROUTE], RunCenterV2Screen)
            self.assertIsInstance(app.screens[PERFORMANCE_V2_ROUTE], PerformanceWorkbenchV2Screen)
            self.assertIsInstance(app.screens[ORCHESTRATOR_V2_ROUTE], ExecutionOrchestratorV2Screen)
            self.assertIsInstance(app.screens[ERD_V2_ROUTE], ERDDesignerV2Screen)
            self.assertIsInstance(app.screens[LOCATION_V2_ROUTE], LocationSelectorV2Screen)
            self.assertIsInstance(app.screens[GENERATION_GUIDE_V2_ROUTE], GenerationBehaviorsGuideV2Screen)

            for route in sorted(expected_routes):
                app.show_screen(route)
                self.assertEqual(app.current_screen_name, route)

            retired_routes = [
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
            for route in retired_routes:
                with self.assertRaises(KeyError):
                    app.show_screen(route)

            guide_titles = {entry[0] for entry in GENERATION_BEHAVIOR_GUIDE}
            self.assertIn("sample_csv generator", guide_titles)
            self.assertIn("derived_expr safe formula generator", guide_titles)
            self.assertIn("Business key + SCD table behaviors", guide_titles)
            self.assertIn("state_transition lifecycle generator", guide_titles)
            self.assertIn("DG03 cross-table temporal integrity planner", guide_titles)
            self.assertIn("DG05 attribute-aware FK selection", guide_titles)
            self.assertIn("DG08 child-cardinality distribution modeling", guide_titles)
            self.assertIn("DG06 missingness + data-quality profiles", guide_titles)
            self.assertIn("DG07 sample-driven profile fitting", guide_titles)
            self.assertIn("DG09 locale-coherent identity bundles", guide_titles)

            schema_screen = app.screens[SCHEMA_V2_ROUTE]
            self.assertTrue(hasattr(schema_screen, "preview_table"))
            self.assertTrue(hasattr(schema_screen, "shortcut_manager"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
