import tempfile
from pathlib import Path
import unittest

from src.experimental.pyqt_schema_project.controller import PyQtSchemaProjectController


class TestPyQtSchemaController(unittest.TestCase):
    def test_default_project_validates(self) -> None:
        controller = PyQtSchemaProjectController()
        ok, message = controller.validate_current()
        self.assertTrue(ok)
        self.assertIn("Fix:", message)

    def test_table_column_and_fk_mutations(self) -> None:
        controller = PyQtSchemaProjectController()
        controller.add_table(table_name="orders", row_count=20)
        controller.add_column(
            table_name="orders",
            column=controller.build_column_spec(name="entity_id", dtype="int", nullable=False),
        )
        controller.add_foreign_key(
            child_table="orders",
            child_column="entity_id",
            parent_table="entities",
            parent_column="entity_id",
            min_children=1,
            max_children=3,
        )
        self.assertIn("orders", controller.table_names())
        self.assertEqual(len(controller.foreign_key_rows()), 1)

    def test_generate_preview_is_deterministic(self) -> None:
        controller = PyQtSchemaProjectController()
        controller.add_table(table_name="orders", row_count=5)
        controller.add_column(
            table_name="orders",
            column=controller.build_column_spec(name="entity_id", dtype="int", nullable=False),
        )
        controller.add_foreign_key(
            child_table="orders",
            child_column="entity_id",
            parent_table="entities",
            parent_column="entity_id",
            min_children=1,
            max_children=1,
        )
        first = controller.generate_preview(row_limit=200)
        second = controller.generate_preview(row_limit=200)
        self.assertEqual(first, second)

    def test_new_float_dtype_is_blocked_for_gui_authoring(self) -> None:
        controller = PyQtSchemaProjectController()
        with self.assertRaises(ValueError) as ctx:
            controller.build_column_spec(name="amount", dtype="float")
        self.assertIn("Fix:", str(ctx.exception))

    def test_generator_form_merge_preserves_passthrough(self) -> None:
        controller = PyQtSchemaProjectController()
        merged = controller.merge_generator_form_values(
            generator_id="uniform_int",
            dtype="int",
            params_json='{"min": 1, "max": 9, "unknown_x": "keep"}',
            form_values={"min": "2", "max": "8"},
        )
        self.assertEqual(merged["min"], 2)
        self.assertEqual(merged["max"], 8)
        self.assertEqual(merged["unknown_x"], "keep")

    def test_mode_downgrade_message_reports_preservation(self) -> None:
        controller = PyQtSchemaProjectController()
        controller.set_schema_design_mode("complex")
        message = controller.set_schema_design_mode("simple")
        self.assertIn("Preserved", message)

    def test_export_csv_and_sqlite_run_with_canonical_runtime(self) -> None:
        controller = PyQtSchemaProjectController()
        with tempfile.TemporaryDirectory() as tmp_dir:
            folder = Path(tmp_dir) / "csv_out"
            db_path = Path(tmp_dir) / "out.db"
            csv_paths = controller.export_csv(str(folder))
            sqlite_counts = controller.export_sqlite(str(db_path))
            self.assertIn("entities", csv_paths)
            self.assertTrue(db_path.exists())
            self.assertIn("entities", sqlite_counts)


if __name__ == "__main__":
    unittest.main()
