import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_schema_project import (
    PATTERN_PRESET_CUSTOM,
    default_generator_params_template,
    valid_generators_for_dtype,
    SchemaProjectDesignerScreen,
)


class _DummyApp:
    def go_home(self) -> None:
        return


class TestGUIGeneratorFiltering(unittest.TestCase):
    def test_valid_generators_for_dtype_filters_expected_options(self):
        decimal_generators = valid_generators_for_dtype("decimal")
        self.assertIn("uniform_float", decimal_generators)
        self.assertIn("normal", decimal_generators)
        self.assertIn("lognormal", decimal_generators)
        self.assertIn("money", decimal_generators)
        self.assertNotIn("timestamp_utc", decimal_generators)

        text_generators = valid_generators_for_dtype("text")
        self.assertIn("sample_csv", text_generators)
        self.assertIn("choice_weighted", text_generators)
        self.assertIn("ordered_choice", text_generators)
        self.assertIn("hierarchical_category", text_generators)
        self.assertNotIn("uniform_int", text_generators)

        int_generators = valid_generators_for_dtype("int")
        self.assertIn("ordered_choice", int_generators)

        bool_generators = valid_generators_for_dtype("bool")
        self.assertEqual(bool_generators, ["", "if_then"])

        bytes_generators = valid_generators_for_dtype("bytes")
        self.assertEqual(bytes_generators, [""])

    def test_default_generator_params_template_handles_time_offset_by_dtype(self):
        date_template = default_generator_params_template("time_offset", "date")
        self.assertIsNotNone(date_template)
        self.assertIn("min_days", date_template)
        self.assertIn("max_days", date_template)
        self.assertNotIn("min_seconds", date_template)

        datetime_template = default_generator_params_template("time_offset", "datetime")
        self.assertIsNotNone(datetime_template)
        self.assertIn("min_seconds", datetime_template)
        self.assertIn("max_seconds", datetime_template)
        self.assertNotIn("min_days", datetime_template)

    def test_default_generator_params_template_handles_ordered_choice(self):
        template = default_generator_params_template("ordered_choice", "text")
        self.assertIsNotNone(template)
        assert template is not None
        self.assertIn("orders", template)
        self.assertIn("order_weights", template)
        self.assertIn("move_weights", template)
        self.assertIn("start_index", template)

    def test_invalid_generator_for_dtype_has_actionable_error(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return

        root.withdraw()
        try:
            screen = SchemaProjectDesignerScreen(root, _DummyApp(), AppConfig())
            screen.col_name_var.set("flag")
            screen.col_dtype_var.set("bool")
            screen.col_generator_var.set("normal")

            with self.assertRaises(ValueError) as ctx:
                screen._column_spec_from_editor(action_prefix="Add column")

            msg = str(ctx.exception)
            self.assertIn("Add column / Generator", msg)
            self.assertIn("generator 'normal' is not valid for dtype 'bool'", msg)
            self.assertIn("Fix:", msg)
        finally:
            root.destroy()

    def test_pattern_preset_populates_pattern_field(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return

        root.withdraw()
        try:
            screen = SchemaProjectDesignerScreen(root, _DummyApp(), AppConfig())
            screen.col_pattern_preset_var.set("Lowercase word (5-14)")
            screen._on_pattern_preset_selected()
            self.assertEqual(screen.col_pattern_var.get(), r"^[a-z]{5,14}$")

            screen.col_pattern_var.set(r"^custom$")
            screen._sync_pattern_preset_from_pattern()
            self.assertEqual(screen.col_pattern_preset_var.get(), PATTERN_PRESET_CUSTOM)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
