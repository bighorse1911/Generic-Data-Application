import tkinter as tk
import unittest

from src.gui_kit.feedback import NotificationCenter


class TestGuiKitNotifications(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_notification_center_tracks_history_and_limits_visible_cards(self) -> None:
        center = NotificationCenter(self.root, default_duration_ms=1000, max_toasts=2, max_history=10)
        center.notify("first")
        center.notify("second", level="success")
        center.notify("third", level="warn")
        self.root.update()

        self.assertEqual(len(center._cards), 2)
        history = center.history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[-1].message, "third")
        self.assertEqual(history[-1].level, "warn")

    def test_notification_history_dialog_renders_entries(self) -> None:
        center = NotificationCenter(self.root)
        center.notify("Saved profile.", level="success")
        center.notify("Run cancelled.", level="warn")
        center.show_history_dialog(title="Test Notifications")
        self.root.update()

        self.assertIsNotNone(center._history_dialog)
        self.assertIsNotNone(center._history_tree)
        assert center._history_tree is not None
        self.assertEqual(len(center._history_tree.get_children()), 2)

    def test_notification_history_has_bounded_size(self) -> None:
        center = NotificationCenter(self.root, max_history=3)
        center.notify("one")
        center.notify("two")
        center.notify("three")
        center.notify("four")

        messages = [entry.message for entry in center.history()]
        self.assertEqual(messages, ["two", "three", "four"])


if __name__ == "__main__":
    unittest.main()
