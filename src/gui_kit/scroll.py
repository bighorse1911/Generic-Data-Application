import tkinter as tk
from tkinter import ttk


def wheel_units_from_delta(delta: int) -> int:
    """
    Convert raw mousewheel delta to Tk scroll units.

    Windows typically emits +/-120 per wheel notch, but some devices emit
    smaller values. We normalize to at least 1 unit per event.
    """
    if delta == 0:
        return 0

    steps = abs(delta) // 120
    if steps == 0:
        steps = 1

    # Positive delta = wheel up = negative yview units.
    return -steps if delta > 0 else steps


class ScrollFrame(ttk.Frame):
    """
    Scrollable container with both vertical and horizontal scrollbars.

    The actual UI content should be added to `self.content`.
    """

    def __init__(self, parent: tk.Widget, *, padding: int = 0) -> None:
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.content = ttk.Frame(self.canvas, padding=padding)
        self._content_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Use global bindings with pointer checks so wheel events work even when
        # focus is on child widgets such as Entry / Combobox.
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_linux_wheel_up, add="+")
        self.bind_all("<Button-5>", self._on_linux_wheel_down, add="+")
        self.bind_all("<Shift-Button-4>", self._on_linux_shift_wheel_up, add="+")
        self.bind_all("<Shift-Button-5>", self._on_linux_shift_wheel_down, add="+")

    def refresh_scrollregion(self) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_content_configure(self, _event=None) -> None:
        self.refresh_scrollregion()
        self._fit_content_width_to_canvas()

    def _on_canvas_configure(self, _event=None) -> None:
        self._fit_content_width_to_canvas()

    def _fit_content_width_to_canvas(self) -> None:
        requested = self.content.winfo_reqwidth()
        visible = self.canvas.winfo_width()
        self.canvas.itemconfigure(self._content_id, width=max(requested, visible))

    def _pointer_inside_self(self) -> bool:
        widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        while widget is not None:
            if widget is self:
                return True
            widget = widget.master
        return False

    def _on_mousewheel(self, event) -> None:
        if not self._pointer_inside_self():
            return
        units = wheel_units_from_delta(event.delta)
        if units != 0:
            self.canvas.yview_scroll(units, "units")

    def _on_shift_mousewheel(self, event) -> None:
        if not self._pointer_inside_self():
            return
        units = wheel_units_from_delta(event.delta)
        if units != 0:
            self.canvas.xview_scroll(units, "units")

    def _on_linux_wheel_up(self, _event) -> None:
        if self._pointer_inside_self():
            self.canvas.yview_scroll(-1, "units")

    def _on_linux_wheel_down(self, _event) -> None:
        if self._pointer_inside_self():
            self.canvas.yview_scroll(1, "units")

    def _on_linux_shift_wheel_up(self, _event) -> None:
        if self._pointer_inside_self():
            self.canvas.xview_scroll(-1, "units")

    def _on_linux_shift_wheel_down(self, _event) -> None:
        if self._pointer_inside_self():
            self.canvas.xview_scroll(1, "units")
