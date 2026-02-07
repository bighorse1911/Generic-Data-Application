import unittest
import tempfile
import os

from src.schema_model import TableSchema, ColumnSpec
from src.schema_io import save_schema_to_json, load_schema_from_json

class TestSchemaIO(unittest.TestCase):
    def test_save_load_roundtrip(self):
        schema = TableSchema(
            table_name="t",
            seed=7,
            columns=[
                ColumnSpec(name="id", dtype="int", primary_key=True, nullable=False),
                ColumnSpec(name="name", dtype="text", nullable=False),
                ColumnSpec(name="score", dtype="float", min_value=0, max_value=1),
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_schema_to_json(schema, path)
            loaded = load_schema_from_json(path)
            self.assertEqual(schema, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

if __name__ == "__main__":
    unittest.main()
