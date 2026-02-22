from dataclasses import asdict
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiSchemaProjectV2Parity(unittest.TestCase):
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

    def _add_non_nullable_column(self, screen, *, name: str, dtype: str) -> None:
        screen.col_name_var.set(name)
        screen.col_dtype_var.set(dtype)
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

    def _run_authoring_scenario(self, screen) -> dict[str, object]:
        screen.project_name_var.set("schema_v2_parity")
        screen.seed_var.set("91")

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
        return str(calls[0][1])

    def _exercise_save_load_and_generate_commands(self, screen) -> tuple[bool, bool, bool]:
        if not screen.project.tables:
            screen._add_table()
        screen.project_name_var.set("schema_v2_parity")
        generated_called = {"value": False}
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = f"{tmp_dir}/schema_project_v2_parity.json"
            with mock.patch("src.gui_schema_core.filedialog.asksaveasfilename", return_value=path):
                saved = bool(screen._save_project())

            screen.project_name_var.set("modified_name")
            with mock.patch("src.gui_schema_core.filedialog.askopenfilename", return_value=path), mock.patch.object(
                screen,
                "confirm_discard_or_save",
                return_value=True,
            ), mock.patch(
                "src.gui_schema_core.messagebox.askyesnocancel",
                return_value=False,
            ) as legacy_prompt:
                screen._load_project()
                self.assertEqual(legacy_prompt.call_count, 0)
            loaded = bool(screen.project_name_var.get() == "schema_v2_parity")

            with mock.patch.object(screen.job_lifecycle, "run_async") as run_async:
                screen._on_generate_project()
                generated_called["value"] = bool(run_async.called)
        return saved, loaded, generated_called["value"]

    def test_schema_project_v2_authoring_flow_builds_expected_project_shape(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        project_payload = self._run_authoring_scenario(screen)
        self.assertEqual(project_payload["name"], "schema_v2_parity")
        self.assertEqual(project_payload["seed"], 91)
        self.assertEqual(len(project_payload["tables"]), 2)
        self.assertEqual(len(project_payload["foreign_keys"]), 1)

    def test_schema_project_v2_error_contract_for_missing_fk_is_actionable(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        msg = self._capture_missing_fk_error(screen)
        self.assertIn("Add relationship", msg)
        self.assertIn("Fix:", msg)

    def test_schema_project_v2_command_paths_save_load_generate(self) -> None:
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        saved, loaded, generated = self._exercise_save_load_and_generate_commands(screen)
        self.assertEqual((saved, loaded, generated), (True, True, True))


if __name__ == "__main__":
    unittest.main()


