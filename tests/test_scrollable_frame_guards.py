"""Test that ScrollableFrame mousewheel handlers guard against destroyed canvas."""
import unittest
import tkinter as tk
from unittest import mock
from src.gui_schema_project import ScrollableFrame


class TestScrollableFrameDestructionGuard(unittest.TestCase):
    """Regression test for TclError when scrolling after canvas destruction."""

    def setUp(self):
        """Create root window for test."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up root window."""
        if self.root.winfo_exists():
            self.root.destroy()

    def test_mousewheel_after_canvas_destroyed(self):
        """Test that _on_mousewheel doesn't crash when canvas is destroyed."""
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        # Simulate destroying the frame (canvas will be destroyed)
        frame.destroy()
        self.root.update()

        # Create a fake event object
        event = type('Event', (), {'delta': 120})()

        # This should NOT raise _tkinter.TclError
        # Before the fix, this would raise: invalid command name ".!tk.!canvas"
        try:
            frame._on_mousewheel(event)
        except tk.TclError:
            self.fail("_on_mousewheel raised TclError after canvas destruction")

    def test_shift_mousewheel_after_canvas_destroyed(self):
        """Test that _on_shift_mousewheel doesn't crash when canvas is destroyed."""
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        frame.destroy()
        self.root.update()

        event = type('Event', (), {'delta': 120})()

        try:
            frame._on_shift_mousewheel(event)
        except tk.TclError:
            self.fail("_on_shift_mousewheel raised TclError after canvas destruction")

    def test_linux_wheel_events_after_canvas_destroyed(self):
        """Test that linux wheel events don't crash when canvas is destroyed."""
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        frame.destroy()
        self.root.update()

        event = type('Event', (), {})()

        try:
            frame._on_linux_wheel_up(event)
            frame._on_linux_wheel_down(event)
        except tk.TclError:
            self.fail("Linux wheel handlers raised TclError after canvas destruction")

    def test_zoom_after_canvas_destroyed(self):
        """Test that zoom methods don't crash when canvas is destroyed."""
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        frame.destroy()
        self.root.update()

        # These should not raise TclError
        try:
            frame.zoom_in()
            frame.zoom_out()
            frame.reset_zoom()
        except tk.TclError:
            self.fail("Zoom methods raised TclError after canvas destruction")

    def test_ctrl_mousewheel_after_canvas_destroyed(self):
        """Test that _on_ctrl_mousewheel doesn't crash when canvas is destroyed."""
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        frame.destroy()
        self.root.update()

        event = type('Event', (), {'delta': 120})()

        try:
            frame._on_ctrl_mousewheel(event)
        except tk.TclError:
            self.fail("_on_ctrl_mousewheel raised TclError after canvas destruction")

    def test_mousewheel_ignores_events_when_pointer_is_outside_frame(self):
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        event = type("Event", (), {"delta": 120})()
        with mock.patch.object(frame, "_pointer_inside_self", return_value=False):
            with mock.patch.object(frame.canvas, "yview_scroll") as yview_scroll:
                frame._on_mousewheel(event)
                yview_scroll.assert_not_called()

    def test_bind_mousewheel_uses_additive_global_bindings(self):
        frame = ScrollableFrame(self.root)
        frame.pack()
        self.root.update()

        with mock.patch.object(frame.canvas, "bind_all") as bind_all:
            frame._bind_mousewheel(frame.canvas)
            bind_all.assert_any_call("<MouseWheel>", frame._on_mousewheel, add="+")
            bind_all.assert_any_call("<Shift-MouseWheel>", frame._on_shift_mousewheel, add="+")
            bind_all.assert_any_call("<Button-4>", frame._on_linux_wheel_up, add="+")
            bind_all.assert_any_call("<Button-5>", frame._on_linux_wheel_down, add="+")
            bind_all.assert_any_call("<Control-MouseWheel>", frame._on_ctrl_mousewheel, add="+")


if __name__ == "__main__":
    unittest.main()
