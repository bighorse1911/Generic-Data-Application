from dataclasses import asdict
import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App


class TestSchemaRouteParity(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self):
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _add_non_nullable_column(self, screen, *, name: str, dtype: str) -> None:
        screen.col_name_var.set(name)
        screen.col_dtype_var.set(dtype)
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

    def _run_authoring_scenario(self, screen) -> dict[str, object]:
        screen.project_name_var.set("schema_route_parity")
        screen.seed_var.set("77")

        screen._add_table()
        parent_table = screen.project.tables[screen.selected_table_index].table_name
        parent_pk = f"{parent_table}_id"
        self._add_non_nullable_column(screen, name="segment", dtype="text")
        self._add_non_nullable_column(screen, name="valid_from", dtype="date")
        self._add_non_nullable_column(screen, name="valid_to", dtype="date")

        screen.table_business_key_var.set(parent_pk)
        screen.table_business_key_static_columns_var.set("")
        screen.table_business_key_changing_columns_var.set("segment")
        screen.table_scd_mode_var.set("scd2")
        screen.table_scd_tracked_columns_var.set("segment")
        screen.table_scd_active_from_var.set("valid_from")
        screen.table_scd_active_to_var.set("valid_to")
        screen._apply_table_changes()

        screen._add_table()
        child_table = screen.project.tables[screen.selected_table_index].table_name
        child_fk_column = f"{parent_table}_id"
        self._add_non_nullable_column(screen, name=child_fk_column, dtype="int")

        screen.fk_parent_table_var.set(parent_table)
        screen.fk_child_table_var.set(child_table)
        screen.fk_child_column_var.set(child_fk_column)
        screen.fk_min_children_var.set("1")
        screen.fk_max_children_var.set("2")
        screen._add_fk()
        screen._run_validation()
        return asdict(screen.project)

    def _capture_missing_fk_error(self, screen) -> str:
        screen.fk_parent_table_var.set("")
        screen.fk_child_table_var.set("")
        screen.fk_child_column_var.set("")
        calls: list[tuple[str, str]] = []
        screen.error_surface.show_dialog = lambda title, message: calls.append((title, message))
        screen._add_fk()
        self.assertEqual(len(calls), 1)
        _title, message = calls[0]
        return str(message)

    def test_primary_and_legacy_authoring_scenario_are_parity_equivalent(self):
        primary_screen = self.app.screens["schema_project"]
        legacy_screen = self.app.screens["schema_project_legacy"]

        primary_project = self._run_authoring_scenario(primary_screen)
        legacy_project = self._run_authoring_scenario(legacy_screen)

        self.assertEqual(primary_project, legacy_project)

    def test_primary_and_legacy_error_contract_shape_matches(self):
        primary_screen = self.app.screens["schema_project"]
        legacy_screen = self.app.screens["schema_project_legacy"]

        primary_msg = self._capture_missing_fk_error(primary_screen)
        legacy_msg = self._capture_missing_fk_error(legacy_screen)

        self.assertEqual(primary_msg, legacy_msg)
        self.assertIn("Add relationship", primary_msg)
        self.assertIn("Fix:", primary_msg)


if __name__ == "__main__":
    unittest.main()
