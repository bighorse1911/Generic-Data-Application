import unittest

from src.gui_kit.accessibility import FocusController


class _DummyWidget:
    def __init__(self, *, exists: bool = True, viewable: bool = True) -> None:
        self._exists = exists
        self._viewable = viewable
        self.focus_calls = 0

    def winfo_exists(self) -> int:
        return 1 if self._exists else 0

    def winfo_viewable(self) -> int:
        return 1 if self._viewable else 0

    def focus_set(self) -> None:
        self.focus_calls += 1


class TestFocusController(unittest.TestCase):
    def test_add_anchor_requires_non_empty_id(self) -> None:
        controller = FocusController(host=object())  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            controller.add_anchor("", lambda: None)

    def test_focus_next_previous_wrap_and_track_last(self) -> None:
        first = _DummyWidget()
        second = _DummyWidget()
        controller = FocusController(host=object())  # type: ignore[arg-type]
        controller.add_anchor("first", lambda: first)
        controller.add_anchor("second", lambda: second)
        controller.set_default_anchor("first")

        self.assertTrue(controller.focus_default())
        self.assertEqual(first.focus_calls, 1)

        self.assertTrue(controller.focus_next())
        self.assertEqual(second.focus_calls, 1)

        self.assertTrue(controller.focus_previous())
        self.assertEqual(first.focus_calls, 2)

    def test_focus_cycle_skips_non_viewable_anchor(self) -> None:
        hidden = _DummyWidget(viewable=False)
        visible = _DummyWidget()
        controller = FocusController(host=object())  # type: ignore[arg-type]
        controller.add_anchor("hidden", lambda: hidden)
        controller.add_anchor("visible", lambda: visible)
        controller.set_default_anchor("hidden")

        self.assertFalse(controller.focus_default())
        self.assertTrue(controller.focus_next())
        self.assertEqual(visible.focus_calls, 1)

    def test_focus_next_returns_false_when_no_focusable_anchors(self) -> None:
        missing = _DummyWidget(exists=False)
        hidden = _DummyWidget(viewable=False)
        controller = FocusController(host=object())  # type: ignore[arg-type]
        controller.add_anchor("missing", lambda: missing)
        controller.add_anchor("hidden", lambda: hidden)
        controller.set_default_anchor("missing")

        self.assertFalse(controller.focus_default())
        self.assertFalse(controller.focus_next())


if __name__ == "__main__":
    unittest.main()


