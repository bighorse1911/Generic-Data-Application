import unittest

from src.gui_schema_project import GENERATORS
from src.gui_v2.generator_forms import GeneratorFormState
from src.gui_v2.generator_forms import missing_form_specs_for_generators
from src.gui_v2.generator_forms import parse_field_text
from src.gui_v2.generator_forms import split_form_state
from src.gui_v2.generator_forms import visible_fields_for


class TestGuiV2GeneratorForms(unittest.TestCase):
    def test_all_registered_generators_have_v2_form_specs(self):
        missing = missing_form_specs_for_generators(GENERATORS)
        self.assertEqual(missing, [])

    def test_visible_fields_include_cross_cutting_for_bytes(self):
        fields = visible_fields_for("sample_csv", dtype="bytes", include_cross_cutting=True)
        field_ids = [field.field_id for field in fields]
        self.assertIn("min_length", field_ids)
        self.assertIn("max_length", field_ids)
        self.assertIn("null_rate", field_ids)

    def test_split_form_state_preserves_passthrough_unknown_keys(self):
        state = split_form_state(
            "uniform_int",
            dtype="int",
            params={"min": 1, "max": 5, "custom_x": "keep"},
        )
        self.assertIsInstance(state, GeneratorFormState)
        self.assertEqual(state.known_params.get("min"), 1)
        self.assertEqual(state.known_params.get("max"), 5)
        self.assertEqual(state.passthrough_params, {"custom_x": "keep"})

    def test_parse_field_text_handles_scalar_and_float_list(self):
        scalar_spec = next(
            field
            for field in visible_fields_for("if_then", dtype="text")
            if field.field_id == "value"
        )
        self.assertEqual(parse_field_text(scalar_spec, "10"), 10)
        float_list_spec = next(
            field
            for field in visible_fields_for("choice_weighted", dtype="text")
            if field.field_id == "weights"
        )
        self.assertEqual(parse_field_text(float_list_spec, "0.2, 0.8"), [0.2, 0.8])


if __name__ == "__main__":
    unittest.main()
