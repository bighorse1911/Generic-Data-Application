from pathlib import Path
import unittest


TARGET_MODULES = [
    Path("src/gui_schema_project.py"),
    Path("src/gui_schema_project_kit.py"),
    Path("src/gui_tools/erd_designer_view.py"),
    Path("src/gui_tools/location_selector_view.py"),
]


class TestGuiErrorSurfaceStaticGate(unittest.TestCase):
    def test_target_modules_do_not_call_messagebox_error_or_warning_directly(self):
        for module_path in TARGET_MODULES:
            with self.subTest(module=str(module_path)):
                source = module_path.read_text(encoding="utf-8")
                self.assertNotIn("messagebox.showerror(", source)
                self.assertNotIn("messagebox.showwarning(", source)


if __name__ == "__main__":
    unittest.main()
