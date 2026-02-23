import unittest

from src.gui_kit.theme_tokens import V2_THEME, v2_button_options


class TestGuiKitThemeTokens(unittest.TestCase):
    def test_v2_theme_tokens_expose_expected_scales(self) -> None:
        self.assertTrue(V2_THEME.colors.app_bg.startswith("#"))
        self.assertTrue(V2_THEME.colors.nav_active_bg.startswith("#"))
        self.assertGreater(V2_THEME.spacing.lg, V2_THEME.spacing.sm)
        self.assertGreater(V2_THEME.focus.ring_thickness, 0)
        self.assertEqual(V2_THEME.type_scale.page_title[2], "bold")

    def test_button_options_include_focus_and_hierarchy_values(self) -> None:
        primary = v2_button_options("primary")
        self.assertEqual(primary["bg"], V2_THEME.buttons.primary.bg)
        self.assertEqual(primary["highlightcolor"], V2_THEME.focus.ring_color)
        self.assertEqual(primary["highlightthickness"], V2_THEME.focus.ring_thickness)

        secondary = v2_button_options("secondary")
        nav = v2_button_options("nav")
        self.assertEqual(secondary["bg"], V2_THEME.buttons.secondary.bg)
        self.assertEqual(nav["bg"], V2_THEME.buttons.nav.bg)

    def test_invalid_button_role_raises_actionable_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            v2_button_options("danger")
        self.assertIn("unsupported button role", str(ctx.exception))
        self.assertIn("Fix:", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
