import unittest

from src.gui_kit.command_palette import CommandPaletteRegistry


class TestCommandPaletteRegistry(unittest.TestCase):
    def test_dispatch_runs_registered_callback(self) -> None:
        registry = CommandPaletteRegistry()
        calls = {"count": 0}

        registry.register_action(
            "route:home_v2",
            "Go to Home v2",
            lambda: calls.__setitem__("count", calls["count"] + 1),
            subtitle="Route jump",
            keywords=("home", "navigate"),
        )

        self.assertTrue(registry.dispatch("route:home_v2"))
        self.assertEqual(calls["count"], 1)
        self.assertFalse(registry.dispatch("route:missing"))

    def test_search_prefers_exact_and_prefix_matches(self) -> None:
        registry = CommandPaletteRegistry()
        registry.register_action(
            "run:benchmark",
            "Run benchmark",
            lambda: None,
            subtitle="Performance Workbench v2 action",
            keywords=("benchmark", "performance"),
        )
        registry.register_action(
            "run:plan",
            "Build partition plan",
            lambda: None,
            subtitle="Run Center v2 action",
            keywords=("plan", "partition"),
        )

        results = registry.search("run bench", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].action_id, "run:benchmark")

    def test_search_supports_keyword_tokens(self) -> None:
        registry = CommandPaletteRegistry()
        registry.register_action(
            "schema:validate",
            "Run validation",
            lambda: None,
            subtitle="Schema Project v2 action",
            keywords=("schema", "check"),
        )
        registry.register_action(
            "schema:save",
            "Save project JSON",
            lambda: None,
            subtitle="Schema Project v2 action",
            keywords=("schema", "save"),
        )

        results = registry.search("schema check", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].action_id, "schema:validate")

    def test_register_rejects_duplicate_action_ids(self) -> None:
        registry = CommandPaletteRegistry()
        registry.register_action("route:home_v2", "Go to Home v2", lambda: None)
        with self.assertRaises(ValueError):
            registry.register_action("route:home_v2", "Go to Home v2 duplicate", lambda: None)


if __name__ == "__main__":
    unittest.main()
