import ast
from pathlib import Path
import unittest


TARGET_MODULES = [
    Path("src/gui_schema_core.py"),
    Path("src/gui_schema_editor_base.py"),
    Path("src/gui_tools/erd_designer_view.py"),
    Path("src/gui_tools/location_selector_view.py"),
]

# Coverage handoff:
# - No test removals in this module.
# - Quality hardening only: static gate now uses AST call inspection.


class TestGuiErrorSurfaceStaticGate(unittest.TestCase):
    @staticmethod
    def _forbidden_messagebox_calls(source: str) -> list[str]:
        tree = ast.parse(source)
        forbidden: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in {"showerror", "showwarning", "showinfo"}:
                continue
            target = func.value
            if isinstance(target, ast.Name) and target.id == "messagebox":
                forbidden.append(func.attr)
            elif isinstance(target, ast.Attribute) and target.attr == "messagebox":
                forbidden.append(func.attr)
        return forbidden

    def test_target_modules_do_not_call_messagebox_error_or_warning_directly(self):
        for module_path in TARGET_MODULES:
            with self.subTest(module=str(module_path)):
                source = module_path.read_text(encoding="utf-8")
                forbidden = self._forbidden_messagebox_calls(source)
                self.assertEqual(
                    forbidden,
                    [],
                    msg=(
                        f"Module '{module_path}' must not call tkinter messagebox directly. "
                        "Fix: route through ErrorSurface/notification helpers."
                    ),
                )


if __name__ == "__main__":
    unittest.main()


