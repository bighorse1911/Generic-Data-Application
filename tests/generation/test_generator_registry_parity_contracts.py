from __future__ import annotations

import importlib
import unittest


EXPECTED_GENERATORS = {
    "latitude",
    "longitude",
    "money",
    "percent",
    "date",
    "timestamp_utc",
    "sample_csv",
    "if_then",
    "hierarchical_category",
    "time_offset",
    "normal",
    "uniform_int",
    "uniform_float",
    "lognormal",
    "choice_weighted",
    "ordered_choice",
    "state_transition",
    "derived_expr",
    "salary_from_age",
}


class GeneratorRegistryParityContractsTests(unittest.TestCase):
    def test_module_symbol_surface(self) -> None:
        mod = importlib.import_module("src.generation.generator_registry")
        required = (
            "GenContext",
            "GeneratorFn",
            "REGISTRY",
            "register",
            "get_generator",
            "reset_runtime_generator_state",
            "gen_latitude",
            "gen_longitude",
            "gen_money",
            "gen_percent",
            "gen_date",
            "gen_timestamp_utc",
            "gen_sample_csv",
            "gen_if_then",
            "gen_hierarchical_category",
            "gen_time_offset",
            "gen_normal",
            "gen_uniform_int",
            "gen_uniform_float",
            "gen_lognormal",
            "gen_choice_weighted",
            "gen_ordered_choice",
            "gen_state_transition",
            "gen_derived_expr",
            "gen_salary_from_age",
        )
        for name in required:
            self.assertTrue(hasattr(mod, name), f"Missing symbol on generator registry facade: {name}")

    def test_registry_contains_expected_builtins(self) -> None:
        mod = importlib.import_module("src.generation.generator_registry")
        mod._bootstrap_builtin_generators()

        registry_keys = set(mod.REGISTRY.keys())
        self.assertTrue(
            EXPECTED_GENERATORS.issubset(registry_keys),
            f"Missing builtins from REGISTRY: {sorted(EXPECTED_GENERATORS - registry_keys)}",
        )

        for generator_name in EXPECTED_GENERATORS:
            fn = mod.get_generator(generator_name)
            self.assertTrue(callable(fn), f"Registry entry is not callable: {generator_name}")

    def test_bootstrap_is_idempotent(self) -> None:
        mod = importlib.import_module("src.generation.generator_registry")
        before = set(mod.REGISTRY.keys())
        mod._bootstrap_builtin_generators()
        mid = set(mod.REGISTRY.keys())
        mod._bootstrap_builtin_generators()
        after = set(mod.REGISTRY.keys())

        self.assertEqual(before, mid)
        self.assertEqual(mid, after)


if __name__ == "__main__":
    unittest.main()
