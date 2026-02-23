import tempfile
import unittest
from pathlib import Path

from src.gui_kit.preferences import WorkspacePreferencesStore


class TestGuiKitPreferences(unittest.TestCase):
    def test_route_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "workspace_state.json"
            store = WorkspacePreferencesStore(path=path)
            payload = {
                "main_tab_index": 1,
                "panel_state": {"project": True, "columns": False},
                "preview_page_size": "500",
            }
            saved = store.save_route_state("schema_project_v2", payload)
            self.assertTrue(saved)
            self.assertTrue(path.exists())

            reloaded = WorkspacePreferencesStore(path=path)
            loaded = reloaded.get_route_state("schema_project_v2")
            self.assertEqual(loaded.get("main_tab_index"), 1)
            self.assertEqual(loaded.get("preview_page_size"), "500")
            panel_state = loaded.get("panel_state")
            self.assertIsInstance(panel_state, dict)
            assert isinstance(panel_state, dict)
            self.assertEqual(panel_state.get("project"), True)
            self.assertEqual(panel_state.get("columns"), False)


if __name__ == "__main__":
    unittest.main()
