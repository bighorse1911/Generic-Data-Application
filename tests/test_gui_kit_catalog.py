import importlib
import unittest

import src.gui_kit as gui_kit


class TestGUIKitComponentCatalog(unittest.TestCase):
    def test_catalog_entries_have_required_fields(self):
        catalog = gui_kit.get_component_catalog()
        self.assertIsInstance(catalog, tuple)
        self.assertGreater(len(catalog), 0)

        expected_keys = {"export", "module", "kind", "summary"}
        for index, component in enumerate(catalog, start=1):
            self.assertEqual(
                set(component.keys()),
                expected_keys,
                msg=f"Catalog entry #{index} must only include {sorted(expected_keys)}.",
            )
            for key in expected_keys:
                self.assertTrue(
                    component[key].strip(),
                    msg=(
                        f"Catalog entry #{index} has blank '{key}'. "
                        "Fix: provide a non-empty string value."
                    ),
                )

    def test_catalog_exports_are_public_and_importable(self):
        expected_exports = {
            "BaseScreen",
            "CollapsiblePanel",
            "ColumnChooserDialog",
            "FormBuilder",
            "InlineValidationEntry",
            "InlineValidationSummary",
            "JsonEditorDialog",
            "SearchEntry",
            "ShortcutManager",
            "ScrollFrame",
            "TableView",
            "ToastCenter",
            "TokenEntry",
            "Tabs",
            "parse_json_text",
            "wheel_units_from_delta",
        }
        catalog_exports: set[str] = set()

        for component in gui_kit.get_component_catalog():
            export = component["export"]
            module_name = component["module"]
            catalog_exports.add(export)

            self.assertIn(
                export,
                gui_kit.__all__,
                msg=(
                    f"Catalog export '{export}' is missing from src.gui_kit.__all__. "
                    "Fix: expose the symbol publicly or remove the catalog entry."
                ),
            )
            self.assertTrue(
                hasattr(gui_kit, export),
                msg=(
                    f"Catalog export '{export}' is not available in src.gui_kit. "
                    "Fix: import and re-export it in src/gui_kit/__init__.py."
                ),
            )

            module = importlib.import_module(module_name)
            self.assertTrue(
                hasattr(module, export),
                msg=(
                    f"Catalog export '{export}' is not present in module '{module_name}'. "
                    "Fix: point to the correct module or export name."
                ),
            )

        self.assertEqual(
            catalog_exports,
            expected_exports,
            msg=(
                "The gui_kit catalog exports changed unexpectedly. "
                "Fix: update this test and dependent tooling intentionally."
            ),
        )


if __name__ == "__main__":
    unittest.main()
