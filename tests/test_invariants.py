import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.generator_project import generate_project_rows
from src.gui_home import (
    App,
    ERDDesignerScreen,
    ExecutionOrchestratorScreen,
    GENERATION_BEHAVIOR_GUIDE,
    GenerationBehaviorsGuideScreen,
    LocationSelectorScreen,
    PerformanceWorkbenchScreen,
)
from src.gui_v2_redesign import (
    ERDDesignerV2BridgeScreen,
    ERDDesignerV2Screen,
    GenerationBehaviorsGuideV2BridgeScreen,
    GenerationBehaviorsGuideV2Screen,
    HomeV2Screen,
    LocationSelectorV2BridgeScreen,
    LocationSelectorV2Screen,
    RunCenterV2Screen,
    SchemaStudioV2Screen,
)
from src.gui_schema_project import (
    DTYPES,
    EXPORT_OPTION_CSV,
    EXPORT_OPTION_SQLITE,
    GENERATORS,
    validate_export_option,
)
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen
from src.schema_project_io import load_project_from_json, save_project_to_json
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec, validate_project
from src.storage_sqlite_project import create_tables, insert_project_rows


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

            self.assertTrue(
                all(v is not None for v in values),
                f"Invariant failed: PK contains nulls in table '{table.table_name}'. "
                "Fix: ensure primary_key columns are always generated with non-null values.",
            )
            self.assertEqual(
                len(values),
                len(set(values)),
                f"Invariant failed: duplicate PK values in table '{table.table_name}'. "
                "Fix: ensure PK generation stays unique per table.",
            )

    def test_foreign_keys_always_exist_in_parent(self):
        project = self._project(seed=21)
        rows = generate_project_rows(project)

        for fk in project.foreign_keys:
            parent_values = {r[fk.parent_column] for r in rows[fk.parent_table]}
            for child_row in rows[fk.child_table]:
                child_val = child_row[fk.child_column]
                self.assertIn(
                    child_val,
                    parent_values,
                    f"Invariant failed: FK value '{child_val}' missing from "
                    f"parent '{fk.parent_table}.{fk.parent_column}'. "
                    "Fix: keep parent rows generated before children and assign FKs from parent PK set.",
                )

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

            for parent_id, count in counts_by_parent.items():
                self.assertGreaterEqual(
                    count,
                    fk.min_children,
                    f"Invariant failed: parent id {parent_id} has only {count} children in '{fk.child_table}'. "
                    f"Expected at least {fk.min_children}. Fix: enforce min_children during FK assignment.",
                )
                self.assertLessEqual(
                    count,
                    fk.max_children,
                    f"Invariant failed: parent id {parent_id} has {count} children in '{fk.child_table}'. "
                    f"Expected at most {fk.max_children}. Fix: enforce max_children during FK assignment.",
                )

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
            with open(path, "w", encoding="utf-8") as f:
                import json

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
        self.assertIn("min_value cannot exceed max_value", msg)
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
        self.assertIn("unknown generator 'not_registered'", msg)
        self.assertIn("Fix:", msg)

    def test_export_option_validation_accepts_supported_values(self):
        self.assertEqual(validate_export_option(EXPORT_OPTION_CSV), EXPORT_OPTION_CSV)
        self.assertEqual(validate_export_option(f"  {EXPORT_OPTION_SQLITE}  "), EXPORT_OPTION_SQLITE)

    def test_export_option_validation_error_has_location_and_hint(self):
        with self.assertRaises(ValueError) as ctx:
            validate_export_option("Parquet")

        msg = str(ctx.exception)
        self.assertIn("Generate / Preview / Export / SQLite panel", msg)
        self.assertIn("unsupported export option", msg)
        self.assertIn("Fix: choose one of", msg)
        self.assertIn(EXPORT_OPTION_CSV, msg)
        self.assertIn(EXPORT_OPTION_SQLITE, msg)

    def test_direction3_gui_lists_decimal_and_semantic_numeric_generators(self):
        self.assertIn("decimal", DTYPES)
        self.assertIn("bytes", DTYPES)
        self.assertNotIn("float", DTYPES)
        self.assertIn("money", GENERATORS)
        self.assertIn("percent", GENERATORS)
        self.assertIn("if_then", GENERATORS)
        self.assertIn("time_offset", GENERATORS)
        self.assertIn("hierarchical_category", GENERATORS)
        self.assertIn("uniform_int", GENERATORS)
        self.assertIn("uniform_float", GENERATORS)
        self.assertIn("normal", GENERATORS)
        self.assertIn("lognormal", GENERATORS)
        self.assertIn("choice_weighted", GENERATORS)
        self.assertIn("ordered_choice", GENERATORS)

    def test_gui_navigation_contract(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return

        root.withdraw()
        try:
            app = App(root, AppConfig())
            self.assertIn("home", app.screens)
            self.assertIn("schema_project", app.screens)
            self.assertIn("schema_project_kit", app.screens)
            self.assertIn("schema_project_legacy", app.screens)
            self.assertIn("generation_behaviors_guide", app.screens)
            self.assertIn("erd_designer", app.screens)
            self.assertIn("location_selector", app.screens)
            self.assertIn("performance_workbench", app.screens)
            self.assertIn("execution_orchestrator", app.screens)
            self.assertIn("home_v2", app.screens)
            self.assertIn("schema_studio_v2", app.screens)
            self.assertIn("run_center_v2", app.screens)
            self.assertIn("erd_designer_v2", app.screens)
            self.assertIn("location_selector_v2", app.screens)
            self.assertIn("generation_behaviors_guide_v2", app.screens)
            self.assertIn("erd_designer_v2_bridge", app.screens)
            self.assertIn("location_selector_v2_bridge", app.screens)
            self.assertIn("generation_behaviors_guide_v2_bridge", app.screens)
            self.assertIsInstance(app.screens["schema_project"], SchemaProjectDesignerKitScreen)
            self.assertIs(app.screens["schema_project"], app.screens["schema_project_kit"])
            self.assertIsInstance(app.screens["generation_behaviors_guide"], GenerationBehaviorsGuideScreen)
            self.assertIsInstance(app.screens["erd_designer"], ERDDesignerScreen)
            self.assertIsInstance(app.screens["location_selector"], LocationSelectorScreen)
            self.assertIsInstance(app.screens["performance_workbench"], PerformanceWorkbenchScreen)
            self.assertIsInstance(app.screens["execution_orchestrator"], ExecutionOrchestratorScreen)
            self.assertIsInstance(app.screens["home_v2"], HomeV2Screen)
            self.assertIsInstance(app.screens["schema_studio_v2"], SchemaStudioV2Screen)
            self.assertIsInstance(app.screens["run_center_v2"], RunCenterV2Screen)
            self.assertIsInstance(app.screens["erd_designer_v2"], ERDDesignerV2Screen)
            self.assertIsInstance(app.screens["location_selector_v2"], LocationSelectorV2Screen)
            self.assertIsInstance(
                app.screens["generation_behaviors_guide_v2"],
                GenerationBehaviorsGuideV2Screen,
            )
            self.assertIsInstance(app.screens["erd_designer_v2_bridge"], ERDDesignerV2BridgeScreen)
            self.assertIsInstance(app.screens["location_selector_v2_bridge"], LocationSelectorV2BridgeScreen)
            self.assertIsInstance(
                app.screens["generation_behaviors_guide_v2_bridge"],
                GenerationBehaviorsGuideV2BridgeScreen,
            )
            self.assertTrue(hasattr(app.screens["performance_workbench"], "diagnostics_tree"))
            self.assertTrue(hasattr(app.screens["performance_workbench"], "chunk_plan_tree"))
            self.assertTrue(hasattr(app.screens["performance_workbench"], "run_benchmark_btn"))
            self.assertTrue(hasattr(app.screens["performance_workbench"], "run_generate_btn"))
            self.assertTrue(hasattr(app.screens["performance_workbench"], "cancel_run_btn"))
            self.assertTrue(hasattr(app.screens["execution_orchestrator"], "partition_tree"))
            self.assertTrue(hasattr(app.screens["execution_orchestrator"], "worker_tree"))
            self.assertTrue(hasattr(app.screens["execution_orchestrator"], "failures_tree"))
            self.assertTrue(hasattr(app.screens["execution_orchestrator"], "start_run_btn"))
            self.assertTrue(hasattr(app.screens["execution_orchestrator"], "start_fallback_btn"))
            self.assertTrue(hasattr(app.screens["execution_orchestrator"], "cancel_run_btn"))
            self.assertTrue(hasattr(app.screens["schema_studio_v2"], "shell"))
            self.assertTrue(hasattr(app.screens["schema_studio_v2"], "section_tabs"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "progress"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "preview_table"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "diagnostics_tree"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "estimate_btn"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "run_benchmark_btn"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "start_run_btn"))
            self.assertTrue(hasattr(app.screens["run_center_v2"], "cancel_run_btn"))
            self.assertTrue(hasattr(app.screens["erd_designer_v2"], "tool"))
            self.assertTrue(hasattr(app.screens["location_selector_v2"], "tool"))
            self.assertTrue(hasattr(app.screens["generation_behaviors_guide_v2"], "tool"))
            self.assertTrue(hasattr(app.screens["erd_designer_v2_bridge"], "launch_btn"))
            self.assertTrue(hasattr(app.screens["location_selector_v2_bridge"], "launch_btn"))
            self.assertTrue(hasattr(app.screens["generation_behaviors_guide_v2_bridge"], "launch_btn"))

            guide_titles = {entry[0] for entry in GENERATION_BEHAVIOR_GUIDE}
            self.assertIn("sample_csv generator", guide_titles)
            self.assertIn("if_then conditional generator", guide_titles)
            self.assertIn("time_offset time-aware generator", guide_titles)
            self.assertIn("hierarchical_category generator", guide_titles)
            self.assertIn("ordered_choice sequence generator", guide_titles)
            self.assertIn("Business key + SCD table behaviors", guide_titles)

            app.show_screen("generation_behaviors_guide")
            app.show_screen("erd_designer")
            app.show_screen("location_selector")
            app.show_screen("performance_workbench")
            app.show_screen("execution_orchestrator")
            app.show_screen("home_v2")
            app.show_screen("schema_studio_v2")
            app.show_screen("run_center_v2")
            app.show_screen("erd_designer_v2")
            app.show_screen("location_selector_v2")
            app.show_screen("generation_behaviors_guide_v2")
            app.show_screen("erd_designer_v2_bridge")
            app.show_screen("location_selector_v2_bridge")
            app.show_screen("generation_behaviors_guide_v2_bridge")
            app.show_screen("home")

            erd_screen = app.screens["erd_designer"]
            erd_screen.schema_name_var.set("erd_gui_test")
            erd_screen.schema_seed_var.set("77")
            erd_screen._create_new_schema()
            self.assertIsNotNone(erd_screen.project)
            self.assertEqual(erd_screen.project.name, "erd_gui_test")

            self.assertFalse(erd_screen._authoring_collapsed)
            erd_screen._toggle_authoring_panel()
            self.assertTrue(erd_screen._authoring_collapsed)
            erd_screen._toggle_authoring_panel()
            self.assertFalse(erd_screen._authoring_collapsed)

            erd_screen.edit_table_current_var.set("")
            erd_screen.edit_table_name_var.set("shared_customers")
            erd_screen.edit_table_row_count_var.set("7")
            erd_screen._save_table_shared()
            self.assertTrue(any(t.table_name == "shared_customers" for t in erd_screen.project.tables))

            erd_screen.edit_column_table_var.set("shared_customers")
            erd_screen._on_edit_column_table_changed()
            erd_screen.edit_column_current_var.set("")
            erd_screen.edit_column_name_var.set("shared_customer_id")
            erd_screen.edit_column_dtype_var.set("int")
            erd_screen.edit_column_primary_key_var.set(True)
            erd_screen.edit_column_nullable_var.set(False)
            erd_screen._on_edit_column_pk_changed()
            erd_screen._save_column_shared()
            shared_customers = next(t for t in erd_screen.project.tables if t.table_name == "shared_customers")
            self.assertTrue(any(c.name == "shared_customer_id" for c in shared_customers.columns))

            erd_screen.table_name_var.set("customers")
            erd_screen._add_table()
            erd_screen.table_name_var.set("orders")
            erd_screen._add_table()

            erd_screen.column_table_var.set("customers")
            erd_screen.column_name_var.set("customer_id")
            erd_screen.column_dtype_var.set("int")
            erd_screen.column_primary_key_var.set(True)
            erd_screen._on_column_pk_changed()
            erd_screen._add_column()

            erd_screen.column_table_var.set("orders")
            erd_screen.column_name_var.set("order_id")
            erd_screen.column_dtype_var.set("int")
            erd_screen.column_primary_key_var.set(True)
            erd_screen._on_column_pk_changed()
            erd_screen._add_column()

            erd_screen.column_table_var.set("orders")
            erd_screen.column_name_var.set("customer_id")
            erd_screen.column_dtype_var.set("int")
            erd_screen.column_primary_key_var.set(False)
            erd_screen.column_nullable_var.set(False)
            erd_screen._on_column_pk_changed()
            erd_screen._add_column()

            erd_screen.relationship_child_table_var.set("orders")
            erd_screen._on_relationship_child_table_changed()
            erd_screen.relationship_child_column_var.set("customer_id")
            erd_screen.relationship_parent_table_var.set("customers")
            erd_screen._on_relationship_parent_table_changed()
            erd_screen.relationship_parent_column_var.set("customer_id")
            erd_screen.relationship_min_children_var.set("1")
            erd_screen.relationship_max_children_var.set("3")
            erd_screen._add_relationship()
            self.assertEqual(len(erd_screen.project.foreign_keys), 1)

            erd_screen.edit_table_current_var.set("orders")
            erd_screen._on_edit_table_selected()
            erd_screen.edit_table_name_var.set("sales_orders")
            erd_screen.edit_table_row_count_var.set("12")
            erd_screen._edit_table()
            self.assertTrue(any(t.table_name == "sales_orders" for t in erd_screen.project.tables))

            erd_screen.edit_column_table_var.set("sales_orders")
            erd_screen._on_edit_column_table_changed()
            erd_screen.edit_column_current_var.set("customer_id")
            erd_screen._on_edit_column_selected()
            erd_screen.edit_column_name_var.set("client_id")
            erd_screen.edit_column_dtype_var.set("int")
            erd_screen.edit_column_primary_key_var.set(False)
            erd_screen.edit_column_nullable_var.set(False)
            erd_screen._on_edit_column_pk_changed()
            erd_screen._edit_column()
            sales_orders = next(t for t in erd_screen.project.tables if t.table_name == "sales_orders")
            self.assertTrue(any(c.name == "client_id" for c in sales_orders.columns))

            with tempfile.TemporaryDirectory() as tmp_dir:
                export_path = os.path.join(tmp_dir, "erd_gui_export.json")
                with mock.patch("src.gui_home.filedialog.asksaveasfilename", return_value=export_path):
                    erd_screen._export_schema_json()
                self.assertTrue(os.path.exists(export_path))
                loaded_export = load_project_from_json(export_path)
                self.assertEqual(loaded_export.name, "erd_gui_test")

            schema_screen = app.screens["schema_project"]
            self.assertEqual(schema_screen.export_option_var.get(), EXPORT_OPTION_CSV)
            self.assertEqual(
                tuple(schema_screen.export_option_combo["values"]),
                (EXPORT_OPTION_CSV, EXPORT_OPTION_SQLITE),
            )

            schema_screen.seed_var.set("not_a_number")
            calls: list[tuple[str, str]] = []
            schema_screen.error_surface.show_dialog = lambda title, message: calls.append((title, message))
            schema_screen._run_validation()
            self.assertEqual(len(calls), 1)
            title, message = calls[0]
            self.assertEqual(title, "Schema project error")
            self.assertIn("Project / Seed", message)
            self.assertIn("must be an integer", message)
            self.assertIn("Fix:", message)
            schema_screen.seed_var.set(str(AppConfig().seed))
            schema_screen._run_validation()

            called: list[str] = []
            schema_screen._on_export_csv = lambda: called.append("csv")
            schema_screen._on_create_insert_sqlite = lambda: called.append("sqlite")

            schema_screen.export_option_var.set(EXPORT_OPTION_CSV)
            schema_screen._on_export_data()
            schema_screen.export_option_var.set(EXPORT_OPTION_SQLITE)
            schema_screen._on_export_data()
            self.assertEqual(called, ["csv", "sqlite"])

            schema_screen._add_table()
            before_columns = len(schema_screen.project.tables[0].columns)

            schema_screen.col_name_var.set("bad_min")
            schema_screen.col_dtype_var.set("int")
            schema_screen.col_min_var.set("abc")
            schema_screen.col_max_var.set("")
            calls.clear()
            schema_screen._add_column()
            self.assertEqual(len(calls), 1)
            title, message = calls[0]
            self.assertEqual(title, "Schema project error")
            self.assertIn("Add column / Min value", message)
            self.assertIn("must be numeric", message)
            self.assertIn("Fix:", message)
            self.assertEqual(len(schema_screen.project.tables[0].columns), before_columns)

            schema_screen.col_name_var.set("legacy_score")
            schema_screen.col_dtype_var.set("float")
            calls.clear()
            schema_screen._add_column()
            self.assertEqual(len(calls), 1)
            title, message = calls[0]
            self.assertEqual(title, "Schema project error")
            self.assertIn("Add column / Type", message)
            self.assertIn("dtype 'float' is deprecated", message)
            self.assertIn("dtype='decimal'", message)
            self.assertEqual(len(schema_screen.project.tables[0].columns), before_columns)

            float_warning_project = SchemaProject(
                name="float_warning",
                seed=2,
                tables=[
                    TableSpec(
                        table_name="legacy",
                        row_count=1,
                        columns=[
                            ColumnSpec("id", "int", nullable=False, primary_key=True),
                            ColumnSpec("score", "float", nullable=False, min_value=0.0, max_value=1.0),
                        ],
                    )
                ],
                foreign_keys=[],
            )
            issues = schema_screen._validate_project_detailed(float_warning_project)
            warning_messages = [i.message for i in issues if i.severity == "warn"]
            self.assertTrue(
                any("legacy dtype 'float'" in m and "prefer dtype='decimal'" in m for m in warning_messages),
                "GUI validation should warn when legacy float dtype is used. "
                "Fix: surface a warning with a decimal migration hint for float columns.",
            )

            duplicate_columns_project = SchemaProject(
                name="duplicate_columns",
                seed=9,
                tables=[
                    TableSpec(
                        table_name="dup",
                        row_count=1,
                        columns=[
                            ColumnSpec("dup_id", "int", nullable=False, primary_key=True),
                            ColumnSpec("dup_id", "text", nullable=False),
                        ],
                    )
                ],
                foreign_keys=[],
            )
            dup_issues = schema_screen._validate_project_detailed(duplicate_columns_project)
            duplicate_errors = [i.message for i in dup_issues if i.severity == "error"]
            self.assertTrue(
                any("duplicate column names" in m and "Fix:" in m for m in duplicate_errors),
                "GUI validation errors must include location, issue, and fix hint.",
            )

            dependency_cycle_project = SchemaProject(
                name="dependency_cycle",
                seed=10,
                tables=[
                    TableSpec(
                        table_name="dep_table",
                        row_count=1,
                        columns=[
                            ColumnSpec("dep_id", "int", nullable=False, primary_key=True),
                            ColumnSpec("a", "text", nullable=False, depends_on=["b"]),
                            ColumnSpec("b", "text", nullable=False, depends_on=["a"]),
                        ],
                    )
                ],
                foreign_keys=[],
            )
            dep_issues = schema_screen._validate_project_detailed(dependency_cycle_project)
            dependency_errors = [i.message for i in dep_issues if i.scope == "dependency" and i.severity == "error"]
            self.assertTrue(
                any("circular depends_on" in m and "Fix:" in m for m in dependency_errors),
                "Validation heatmap dependency checks should surface circular dependencies with actionable fixes.",
            )

            scd_issue_project = SchemaProject(
                name="scd_issue",
                seed=11,
                tables=[
                    TableSpec(
                        table_name="dim_table",
                        row_count=1,
                        columns=[
                            ColumnSpec("dim_id", "int", nullable=False, primary_key=True),
                            ColumnSpec("code", "text", nullable=False),
                            ColumnSpec("city", "text", nullable=False),
                        ],
                        business_key=["code"],
                        scd_mode="scd2",
                        scd_tracked_columns=["city"],
                    )
                ],
                foreign_keys=[],
            )
            scd_issues = schema_screen._validate_project_detailed(scd_issue_project)
            scd_errors = [i.message for i in scd_issues if i.scope == "scd" and i.severity == "error"]
            self.assertTrue(
                any("scd_mode='scd2' requires scd_active_from_column and scd_active_to_column" in m for m in scd_errors),
                "Validation heatmap SCD checks should surface missing active period fields.",
            )

            schema_screen.project = dependency_cycle_project
            schema_screen.project_name_var.set(dependency_cycle_project.name)
            schema_screen.seed_var.set(str(dependency_cycle_project.seed))
            schema_screen._run_validation()
            self.assertIn("Dependencies", schema_screen.heatmap._checks)
            self.assertIn("SCD/BK", schema_screen.heatmap._checks)
            dep_table_idx = schema_screen.heatmap._tables.index("dep_table")
            dep_check_idx = schema_screen.heatmap._checks.index("Dependencies")
            dep_cell_msgs = schema_screen.heatmap._cell_details[(dep_table_idx, dep_check_idx)]
            self.assertTrue(
                any("depends_on" in m.lower() for m in dep_cell_msgs),
                "Dependencies heatmap cell should include dependency-specific validation details.",
            )

            with self.assertRaisesRegex(KeyError, "Unknown screen 'missing'"):
                app.show_screen("missing")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
