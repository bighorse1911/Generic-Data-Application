import json
import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


class TestGuiV2SchemaProjectGeneratorUI(unittest.TestCase):
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

    def _ensure_selected_table(self, screen) -> None:
        if screen.selected_table_index is None:
            screen._add_table()
        self.assertIsNotNone(screen.selected_table_index)

    def test_v2_route_has_generator_form_host(self) -> None:
        v2 = self.app.screens[SCHEMA_V2_ROUTE]
        self.assertTrue(hasattr(v2, "generator_form_box"))

    def test_structured_fields_sync_to_params_json_and_preserve_unknown(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        self._ensure_selected_table(screen)

        screen.col_dtype_var.set("int")
        screen.col_generator_var.set("uniform_int")
        screen.col_params_var.set('{"min": 1, "max": 3, "custom_x": "keep"}')

        self.assertIn("min", screen._generator_form_bindings)
        screen._generator_form_bindings["min"].var.set("2")

        payload = json.loads(screen.col_params_var.get())
        self.assertEqual(payload.get("min"), 2)
        self.assertEqual(payload.get("max"), 3)
        self.assertEqual(payload.get("custom_x"), "keep")

    def test_dependency_source_fields_auto_add_depends_on(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        self._ensure_selected_table(screen)

        screen.col_name_var.set("flag")
        screen.col_dtype_var.set("bool")
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

        screen.col_name_var.set("segment_label")
        screen.col_dtype_var.set("text")
        screen.col_generator_var.set("if_then")
        screen._generator_form_bindings["if_column"].var.set("flag")
        screen._generator_form_bindings["value"].var.set("true")
        screen._generator_form_bindings["then_value"].var.set("VIP")
        screen._generator_form_bindings["else_value"].var.set("STD")

        depends_on = [part.strip() for part in screen.col_depends_var.get().split(",") if part.strip()]
        self.assertIn("flag", depends_on)

    def test_save_load_roundtrip_keeps_unknown_generator_params(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        self._ensure_selected_table(screen)

        screen.col_name_var.set("score")
        screen.col_dtype_var.set("int")
        screen.col_generator_var.set("uniform_int")
        screen.col_params_var.set('{"min": 1, "max": 9, "custom_x": "keep"}')
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "v2_generator_roundtrip.json")
            with mock.patch("src.gui_schema_core.filedialog.asksaveasfilename", return_value=path):
                self.assertTrue(screen._save_project())

            screen.project_name_var.set("changed_name")
            with mock.patch("src.gui_schema_core.filedialog.askopenfilename", return_value=path), mock.patch.object(
                screen,
                "confirm_discard_or_save",
                return_value=True,
            ):
                screen._load_project()

            table = screen.project.tables[0]
            score_col = next(column for column in table.columns if column.name == "score")
            assert isinstance(score_col.params, dict)
            self.assertEqual(score_col.params.get("custom_x"), "keep")

    def test_table_correlation_groups_roundtrip_through_table_editor(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        self._ensure_selected_table(screen)

        screen.col_name_var.set("metric_a")
        screen.col_dtype_var.set("decimal")
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

        screen.col_name_var.set("metric_b")
        screen.col_dtype_var.set("decimal")
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

        payload = [
            {
                "group_id": "g_metrics",
                "columns": ["metric_a", "metric_b"],
                "rank_correlation": [[1.0, 0.75], [0.75, 1.0]],
            }
        ]
        screen.table_correlation_groups_var.set(json.dumps(payload))
        screen._apply_table_changes()

        assert screen.selected_table_index is not None
        table = screen.project.tables[screen.selected_table_index]
        self.assertEqual(table.correlation_groups, payload)

    def test_project_timeline_constraints_roundtrip_through_save_load(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        payload = [
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
                        "max_days": 5,
                    }
                ],
            }
        ]
        screen.project = SchemaProject(
            name="dg03_gui_roundtrip",
            seed=123,
            tables=[
                TableSpec(
                    table_name="signup",
                    row_count=2,
                    columns=[
                        ColumnSpec("signup_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("signup_date", "date", nullable=False, generator="date"),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("signup_id", "int", nullable=False),
                        ColumnSpec("ordered_date", "date", nullable=False, generator="date"),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("orders", "signup_id", "signup", "signup_id", 1, 1),
            ],
            timeline_constraints=payload,
        )
        screen._suspend_project_meta_dirty = True
        screen.project_name_var.set(screen.project.name)
        screen.seed_var.set(str(screen.project.seed))
        screen.project_timeline_constraints_var.set(json.dumps(payload))
        screen._suspend_project_meta_dirty = False

        screen._apply_project_vars_to_model()
        self.assertEqual(screen.project.timeline_constraints, payload)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "v2_timeline_roundtrip.json")
            with mock.patch("src.gui_schema_core.filedialog.asksaveasfilename", return_value=path):
                self.assertTrue(screen._save_project())

            screen.project_timeline_constraints_var.set("")
            with mock.patch("src.gui_schema_core.filedialog.askopenfilename", return_value=path), mock.patch.object(
                screen,
                "confirm_discard_or_save",
                return_value=True,
            ):
                screen._load_project()

            self.assertEqual(screen.project.timeline_constraints, payload)
            self.assertEqual(json.loads(screen.project_timeline_constraints_var.get()), payload)


if __name__ == "__main__":
    unittest.main()


