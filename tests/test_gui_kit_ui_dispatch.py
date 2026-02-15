import tkinter as tk
import unittest

from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_kit.ui_dispatch import safe_dispatch


class _FakeWidget:
    def __init__(self) -> None:
        self.alive = True
        self.raise_on_after = False

    def after(self, _ms: int, callback):
        if self.raise_on_after:
            raise tk.TclError("widget destroyed")
        callback()
        return None

    def winfo_exists(self) -> int:
        return 1 if self.alive else 0


class TestUIDispatch(unittest.TestCase):
    def test_safe_dispatch_skips_when_not_alive(self):
        calls: list[str] = []

        def after(_ms: int, callback):
            callback()
            return None

        ok = safe_dispatch(after, lambda: calls.append("ran"), is_alive=lambda: False)
        self.assertFalse(ok)
        self.assertEqual(calls, [])

    def test_safe_dispatch_returns_false_on_tcl_error(self):
        def bad_after(_ms: int, _callback):
            raise tk.TclError("widget destroyed")

        ok = safe_dispatch(bad_after, lambda: None)
        self.assertFalse(ok)

    def test_dispatcher_marshal_runs_when_widget_alive(self):
        widget = _FakeWidget()
        dispatcher = UIDispatcher.from_widget(widget)
        calls: list[int] = []

        callback = dispatcher.marshal(lambda value: calls.append(value))
        callback(7)
        self.assertEqual(calls, [7])

    def test_dispatcher_marshal_drops_when_widget_is_destroyed(self):
        widget = _FakeWidget()
        dispatcher = UIDispatcher.from_widget(widget)
        calls: list[int] = []

        widget.alive = False
        callback = dispatcher.marshal(lambda value: calls.append(value))
        callback(9)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
