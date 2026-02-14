import time
import tkinter as tk
import unittest

from src.gui_kit import SearchEntry, ShortcutManager, ToastCenter, TokenEntry, parse_json_text
from src.gui_home import App
from src.config import AppConfig


class TestGUIKitPhaseAComponents(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_parse_json_text_reports_actionable_location(self):
        value, err = parse_json_text('{"a": 1,', require_object=True)
        self.assertIsNone(value)
        self.assertIsNotNone(err)
        assert err is not None
        self.assertIn("line", err)
        self.assertIn("column", err)
        self.assertIn("Fix:", err)

    def test_search_entry_debounce_emits_latest_query_once(self):
        seen: list[str] = []
        search = SearchEntry(self.root, on_change=lambda q: seen.append(q), delay_ms=20)
        search.pack()
        search.query_var.set("cust")
        search.query_var.set("customer")

        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline and not seen:
            self.root.update()

        self.assertEqual(seen, ["customer"])

    def test_token_entry_syncs_tokens_to_stringvar(self):
        var = tk.StringVar(value="code, segment")
        token = TokenEntry(self.root, textvariable=var)
        token.pack()
        self.root.update()

        self.assertEqual(token.get_tokens(), ["code", "segment"])
        token.entry_var.set("status")
        token._on_commit_event()
        self.assertEqual(var.get(), "code, segment, status")

    def test_toast_center_limits_visible_toasts(self):
        center = ToastCenter(self.root, default_duration_ms=1000, max_toasts=2)
        center.show_toast("one")
        center.show_toast("two")
        center.show_toast("three")
        self.root.update()
        self.assertEqual(len(center._cards), 2)

    def test_shortcut_manager_exposes_help_dialog(self):
        manager = ShortcutManager(self.root)
        manager.register("<F5>", "Run validation", lambda: None)
        manager.show_help_dialog(title="Test shortcuts")
        self.root.update()
        self.assertEqual(manager.items(), [("<F5>", "Run validation")])

    def test_kit_screen_exposes_phase_a_widgets(self):
        app = App(self.root, AppConfig())
        screen = app.screens["schema_project"]
        self.assertTrue(hasattr(screen, "toast_center"))
        self.assertTrue(hasattr(screen, "shortcut_manager"))
        self.assertTrue(hasattr(screen, "tables_search"))
        self.assertTrue(hasattr(screen, "columns_search"))
        self.assertTrue(hasattr(screen, "fk_search"))
        self.assertTrue(hasattr(screen, "table_business_key_entry"))
        self.assertTrue(hasattr(screen, "table_business_key_static_entry"))
        self.assertTrue(hasattr(screen, "table_business_key_changing_entry"))
        self.assertTrue(hasattr(screen, "table_scd_tracked_entry"))
        self.assertTrue(hasattr(screen, "col_params_editor_btn"))


if __name__ == "__main__":
    unittest.main()
