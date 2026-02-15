import unittest

from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import actionable_error
from src.gui_kit.error_surface import is_actionable_message


class TestErrorSurface(unittest.TestCase):
    def test_actionable_error_uses_canonical_shape(self):
        message = actionable_error("Performance Workbench", "Schema path", "path is required", "choose a file")
        self.assertEqual(
            message,
            "Performance Workbench / Schema path: path is required. Fix: choose a file.",
        )

    def test_emit_routes_to_dialog_status_and_inline(self):
        calls: list[str] = []
        surface = ErrorSurface(
            context="Run Center v2",
            dialog_title="Run Center v2 error",
            show_dialog=lambda title, msg: calls.append(f"dialog:{title}:{msg}"),
            set_status=lambda msg: calls.append(f"status:{msg}"),
            set_inline=lambda msg: calls.append(f"inline:{msg}"),
        )

        message = surface.emit(location="Schema path", issue="path is required", hint="choose a file", mode="mixed")
        self.assertIn(message, calls[0])
        self.assertTrue(any(item.startswith("dialog:") for item in calls))
        self.assertTrue(any(item.startswith("status:") for item in calls))
        self.assertTrue(any(item.startswith("inline:") for item in calls))

    def test_emit_exception_uses_raw_exception_text(self):
        calls: list[str] = []
        surface = ErrorSurface(
            context="Execution Orchestrator",
            dialog_title="Execution orchestrator error",
            show_dialog=lambda _title, msg: calls.append(msg),
        )
        message = surface.emit_exception(ValueError("boom"), mode="dialog")
        self.assertEqual(message, "boom")
        self.assertEqual(calls, ["boom"])

    def test_emit_warning_uses_warning_title_when_available(self):
        calls: list[tuple[str, str]] = []
        surface = ErrorSurface(
            context="Location selector",
            dialog_title="Location selector error",
            warning_title="Location selector warning",
            show_warning=lambda title, msg: calls.append((title, msg)),
        )
        message = surface.emit_warning(
            location="Sample points",
            issue="no sampled points are available",
            hint="generate sample points before saving CSV",
            mode="dialog",
        )
        self.assertEqual(calls, [("Location selector warning", message)])
        self.assertTrue(is_actionable_message(message))

    def test_emit_exception_actionable_normalizes_non_actionable_message(self):
        calls: list[str] = []
        surface = ErrorSurface(
            context="Schema project",
            dialog_title="Schema project error",
            show_dialog=lambda _title, msg: calls.append(msg),
        )
        message = surface.emit_exception_actionable(
            "raw failure",
            location="Add column",
            hint="fix column inputs and retry",
            mode="dialog",
        )
        self.assertTrue(is_actionable_message(message))
        self.assertIn("Fix:", message)
        self.assertEqual(calls, [message])


if __name__ == "__main__":
    unittest.main()
