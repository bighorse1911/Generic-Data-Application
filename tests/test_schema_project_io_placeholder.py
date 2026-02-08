import unittest
from pathlib import Path

from src.schema_project_io import load_project_from_json


class TestLoadProjectPlaceholder(unittest.TestCase):
    def test_placeholder_auto_resolves_if_fixture_present(self):
        json_path = Path(__file__).resolve().parent / "fixtures" / "default_schema_project.json"

        project = load_project_from_json(str(json_path))

        # Find any column params that reference a path and assert it's been resolved to an existing file
        found = False
        for t in project.tables:
            for c in t.columns:
                params = c.params or {}
                p = params.get("path")
                if p is not None:
                    found = True
                    self.assertTrue(Path(p).exists(), f"Resolved path does not exist: {p}")
        self.assertTrue(found, "No params.path found in loaded project to validate resolution.")


if __name__ == "__main__":
    unittest.main()
