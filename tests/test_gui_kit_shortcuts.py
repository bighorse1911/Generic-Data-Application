import time
import tkinter as tk
import unittest

from src.gui_kit.shortcuts import ShortcutManager


class TestShortcutManager(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.geometry("220x120")

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _pump(self, duration_seconds: float = 0.05) -> None:
        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            self.root.update()

    def test_activate_deactivate_lifecycle(self) -> None:
        triggered = {"count": 0}
        manager = ShortcutManager(self.root)
        manager.register("<F8>", "Trigger", lambda: triggered.__setitem__("count", triggered["count"] + 1))

        self.assertFalse(manager.is_active)
        manager.activate()
        self.assertTrue(manager.is_active)
        self.assertTrue(manager._bound_ids)
        manager._items[0].callback()
        self.assertEqual(triggered["count"], 1)

        manager.deactivate()
        self.assertFalse(manager.is_active)
        self.assertEqual(manager._bound_ids, {})

        manager._items[0].callback()
        self.assertEqual(triggered["count"], 2)

    def test_help_only_items_are_listed_without_binding(self) -> None:
        manager = ShortcutManager(self.root)
        manager.register("<F1>", "Open help", lambda: None)
        manager.register_help_item("Ctrl/Cmd+Shift+C", "Copy selected rows without headers")

        items = manager.items()
        self.assertIn(("<F1>", "Open help"), items)
        self.assertIn(("Ctrl/Cmd+Shift+C", "Copy selected rows without headers"), items)


if __name__ == "__main__":
    unittest.main()
