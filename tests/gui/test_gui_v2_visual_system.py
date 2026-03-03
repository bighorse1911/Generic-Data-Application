from pathlib import Path
import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_kit.theme_tokens import V2_THEME

# Coverage handoff:
# - No test removals in this module.
# - Quality hardening only: replaced bare assert with explicit failure path.


class TestGuiV2VisualSystem(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_v2_shell_buttons_use_shared_hierarchy_tokens(self) -> None:
        run_center = self.app.screens["run_center_v2"]
        shell = run_center.shell
        self.assertEqual(shell.back_btn.cget("bg"), V2_THEME.buttons.secondary.bg)
        self.assertEqual(shell.back_btn.cget("fg"), V2_THEME.buttons.secondary.fg)
        self.assertEqual(int(shell.back_btn.cget("highlightthickness")), V2_THEME.focus.ring_thickness)
        self.assertEqual(shell.back_btn.cget("highlightcolor"), V2_THEME.focus.ring_color)

        shell.add_nav_button("token_probe", "Token Probe", lambda: None)
        probe = shell._nav_buttons["token_probe"]
        self.assertEqual(probe.cget("bg"), V2_THEME.buttons.nav.bg)
        shell.set_nav_active("token_probe")
        self.assertEqual(probe.cget("bg"), V2_THEME.colors.nav_active_bg)
        self.assertEqual(probe.cget("fg"), V2_THEME.colors.nav_active_fg)

    def test_schema_v2_header_uses_secondary_button_tokens(self) -> None:
        screen = self.app.screens["schema_project_v2"]
        header_host = getattr(screen, "_header_host", None)
        self.assertIsNotNone(header_host)
        if header_host is None:
            self.fail("Schema v2 screen must expose _header_host frame for token assertions.")
        frame_children = [child for child in header_host.winfo_children() if isinstance(child, tk.Frame)]
        self.assertGreaterEqual(len(frame_children), 1)
        header = frame_children[0]
        button_labels = [w for w in header.winfo_children() if isinstance(w, tk.Button)]
        self.assertGreaterEqual(len(button_labels), 2)
        for button in button_labels:
            self.assertEqual(button.cget("bg"), V2_THEME.buttons.secondary.bg)
            self.assertEqual(int(button.cget("highlightthickness")), V2_THEME.focus.ring_thickness)

    def test_v2_screen_modules_do_not_embed_hex_colors_or_font_tuples(self) -> None:
        target_files = [
            Path("src/gui_v2_redesign.py"),
            Path("src/gui_v2_schema_project.py"),
        ]
        for path in target_files:
            with self.subTest(path=str(path)):
                source = path.read_text(encoding="utf-8")
                self.assertNotRegex(source, r"#[0-9a-fA-F]{3,6}")
                self.assertNotIn("font=(", source)


if __name__ == "__main__":
    unittest.main()
