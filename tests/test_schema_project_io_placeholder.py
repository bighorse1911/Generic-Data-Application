import json
import os
import tempfile
import unittest
from pathlib import Path

from src.schema_project_io import load_project_from_json


class TestLoadProjectPlaceholder(unittest.TestCase):
    def test_placeholder_auto_resolves_if_fixture_present(self):
        json_path = Path(__file__).resolve().parent / "fixtures" / "default_schema_project.json"
        repo_root = Path(__file__).resolve().parents[1]

        project = load_project_from_json(str(json_path))

        # Find any column params that reference a path and assert it's been resolved to an existing file
        found = False
        for t in project.tables:
            for c in t.columns:
                params = c.params or {}
                p = params.get("path")
                if p is not None:
                    found = True
                    candidate = Path(p)
                    resolved = candidate if candidate.is_absolute() else (repo_root / candidate)
                    self.assertTrue(resolved.exists(), f"Resolved path does not exist: {p}")
                    self.assertFalse(candidate.is_absolute(), f"Path should be repo-relative, got: {p}")
                    self.assertEqual(
                        candidate.as_posix(),
                        "tests/fixtures/city_country_pool.csv",
                        f"Expected repo-relative fixture path, got: {p}",
                    )
        self.assertTrue(found, "No params.path found in loaded project to validate resolution.")

    def test_load_normalizes_legacy_absolute_fixture_path_to_repo_relative(self):
        repo_root = Path(__file__).resolve().parents[1]
        absolute_fixture_csv = repo_root / "tests" / "fixtures" / "city_country_pool.csv"

        payload = {
            "name": "legacy_absolute_csv_path",
            "seed": 11,
            "tables": [
                {
                    "table_name": "people",
                    "row_count": 2,
                    "columns": [
                        {"name": "id", "dtype": "int", "nullable": False, "primary_key": True},
                        {
                            "name": "city",
                            "dtype": "text",
                            "nullable": False,
                            "generator": "sample_csv",
                            "params": {"path": str(absolute_fixture_csv), "column_index": 0},
                        },
                    ],
                }
            ],
            "foreign_keys": [],
        }

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            project = load_project_from_json(path)
            params = project.tables[0].columns[1].params or {}
            self.assertEqual(params.get("path"), "tests/fixtures/city_country_pool.csv")
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main()
