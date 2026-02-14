import os
import tempfile
import unittest

from src.generator_project import generate_project_rows
from src.gui_schema_project import _csv_export_value
from src.schema_project_io import build_project_sql_ddl
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project
from src.storage_sqlite_project import create_tables, insert_project_rows


class TestExtensibleBytesDtype(unittest.TestCase):
    def _bytes_project(self) -> SchemaProject:
        return SchemaProject(
            name="bytes_dtype",
            seed=303,
            tables=[
                TableSpec(
                    table_name="artifacts",
                    row_count=6,
                    columns=[
                        ColumnSpec("artifact_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "payload",
                            "bytes",
                            nullable=False,
                            params={"min_length": 4, "max_length": 8},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

    def test_bytes_dtype_generation_is_supported_and_deterministic(self):
        project = self._bytes_project()
        validate_project(project)

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        for row in rows_a["artifacts"]:
            payload = row["payload"]
            self.assertIsInstance(payload, bytes)
            self.assertGreaterEqual(len(payload), 4)
            self.assertLessEqual(len(payload), 8)

    def test_sql_and_sqlite_paths_support_bytes_dtype(self):
        project = self._bytes_project()
        ddl = build_project_sql_ddl(project)
        self.assertIn('"payload" BLOB NOT NULL', ddl)

        rows = generate_project_rows(project)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()
        try:
            create_tables(db_path, project)
            inserted = insert_project_rows(db_path, project, rows, chunk_size=500)
            self.assertEqual(inserted, {"artifacts": 6})
        finally:
            try:
                os.remove(db_path)
            except PermissionError:
                pass

    def test_bytes_dtype_validation_error_is_actionable_for_unsupported_choices(self):
        bad = SchemaProject(
            name="bad_bytes_choices",
            seed=1,
            tables=[
                TableSpec(
                    table_name="artifacts",
                    row_count=1,
                    columns=[
                        ColumnSpec("artifact_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("payload", "bytes", nullable=False, choices=["a", "b"]),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'artifacts', column 'payload'", msg)
        self.assertIn("dtype 'bytes' does not support choices", msg)
        self.assertIn("Fix:", msg)

    def test_csv_export_encodes_bytes_as_base64_text(self):
        encoded = _csv_export_value(b"\x00\xff")
        self.assertEqual(encoded, "AP8=")


if __name__ == "__main__":
    unittest.main()
