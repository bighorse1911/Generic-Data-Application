from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from src.gui_kit.scroll import wheel_units_from_delta

class ScrollableFrame(ttk.Frame):
    """
    A ttk.Frame that can scroll both vertically and horizontally.

    Internals:
    - A Canvas does the scrolling.
    - An 'inner' Frame lives inside the Canvas and holds your actual widgets.
    - Scrollbars are attached to the Canvas.
    """
    def __init__(self, parent: tk.Widget, *, padding: int = 0) -> None:
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        # Layout: canvas takes most space, scrollbars on right and bottom
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # Inner frame: where you will place all your widgets
        self.inner = ttk.Frame(self.canvas, padding=padding)
        self._inner_window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # When inner frame resizes, update scrollable area
        self.inner.bind("<Configure>", self._on_inner_configure)
        # When canvas resizes, keep inner frame width synced if desired
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling (Windows/macOS/Linux variants)
        self._bind_mousewheel(self.canvas)

        #Zoom Logic
        self.zoom = 1.0
        self.min_zoom = 0.7
        self.max_zoom = 1.5
        self.zoom_step = 0.1

        #Base font to enable zooming
        self._fonts = {}
        for name in ("TkDefaultFont", "TkTextFont", "TkFixedFont"):
            f = tkfont.nametofont(name)
            self._fonts[name] = {
                "font": f,
                "size": f.cget("size"),
            }


    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        # If you want the inner frame to expand to canvas width, uncomment:
        # self.canvas.itemconfigure(self._inner_window_id, width=event.width)
        # If you want horizontal scrolling to work, do NOT force width.
        pass

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        # Windows: <MouseWheel>, Linux: Button-4/5, macOS uses <MouseWheel> too but delta differs.
        widget.bind_all("<MouseWheel>", self._on_mousewheel, add="+")     # Windows/macOS
        widget.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        widget.bind_all("<Button-4>", self._on_linux_wheel_up, add="+")   # Linux
        widget.bind_all("<Button-5>", self._on_linux_wheel_down, add="+")
        widget.bind_all("<Control-MouseWheel>", self._on_ctrl_mousewheel, add="+")
        widget.bind_all("<Control-plus>", lambda e: self.zoom_in(), add="+")
        widget.bind_all("<Control-minus>", lambda e: self.zoom_out(), add="+")
        widget.bind_all("<Control-0>", lambda e: self.reset_zoom(), add="+")

    def _pointer_inside_self(self) -> bool:
        try:
            widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
        except tk.TclError:
            return False
        while widget is not None:
            if widget is self:
                return True
            widget = widget.master
        return False


    def _on_mousewheel(self, event) -> None:
        # Vertical scroll
        if not self.canvas.winfo_exists() or not self._pointer_inside_self():
            return
        units = wheel_units_from_delta(getattr(event, "delta", 0))
        if units != 0:
            self.canvas.yview_scroll(units, "units")

    def _on_shift_mousewheel(self, event) -> None:
        # Horizontal scroll (hold Shift)
        if not self.canvas.winfo_exists() or not self._pointer_inside_self():
            return
        units = wheel_units_from_delta(getattr(event, "delta", 0))
        if units != 0:
            self.canvas.xview_scroll(units, "units")

    def _on_linux_wheel_up(self, _event) -> None:
        if self.canvas.winfo_exists() and self._pointer_inside_self():
            self.canvas.yview_scroll(-1, "units")

    def _on_linux_wheel_down(self, _event) -> None:
        if self.canvas.winfo_exists() and self._pointer_inside_self():
            self.canvas.yview_scroll(1, "units")
    # Zooming methods
    def zoom_in(self) -> None:
        self._apply_zoom(self.zoom + self.zoom_step)

    def zoom_out(self) -> None:
        self._apply_zoom(self.zoom - self.zoom_step)

    def reset_zoom(self) -> None:
        self._apply_zoom(1.0)
    def _apply_zoom(self, new_zoom: float) -> None:
        if not self.canvas.winfo_exists():
            return
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        if abs(new_zoom - self.zoom) < 0.001:
            return

        self.zoom = new_zoom

        for meta in self._fonts.values():
            base = meta["size"]
            meta["font"].configure(size=int(base * self.zoom))

        # Update scroll region after resizing
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def scale_treeview_columns(tree: ttk.Treeview, factor: float) -> None:
        for col in tree["columns"]:
            w = tree.column(col, "width")
            tree.column(col, width=int(w * factor))


    def _on_ctrl_mousewheel(self, event) -> None:
        if not self.canvas.winfo_exists() or not self._pointer_inside_self():
            return
        delta = getattr(event, "delta", 0)
        if delta > 0:
            self.zoom_in()
        elif delta < 0:
            self.zoom_out()
class CollapsibleSection(ttk.Frame):
    """
    A collapsible panel with a header row and a content frame.

    Usage:
        section = CollapsibleSection(parent, title="Tables")
        section.pack(fill="both", expand=True)
        # put widgets inside:
        ttk.Label(section.content, text="Hello").pack()
    """
    def __init__(self, parent: tk.Widget, title: str, *, start_collapsed: bool = False) -> None:
        super().__init__(parent)

        self._collapsed = tk.BooleanVar(value=start_collapsed)

        # Header
        header = ttk.Frame(self)
        header.pack(fill="x")

        self._btn = ttk.Button(header, width=3, command=self.toggle)
        self._btn.pack(side="left")

        self._title_lbl = ttk.Label(header, text=title, font=("Segoe UI", 10, "bold"))
        self._title_lbl.pack(side="left", padx=(6, 0))

        # Make header clickable too
        self._title_lbl.bind("<Button-1>", lambda e: self.toggle())
        header.bind("<Button-1>", lambda e: self.toggle())

        # Content
        self.content = ttk.Frame(self)
        if not start_collapsed:
            self.content.pack(fill="both", expand=True, pady=(6, 0))

        self._sync_button()

    def _sync_button(self) -> None:
        # ▾ expanded, ▸ collapsed
        self._btn.configure(text="▸" if self._collapsed.get() else "▾")

    def toggle(self) -> None:
        if self._collapsed.get():
            self.expand()
        else:
            self.collapse()

    def collapse(self) -> None:
        if not self._collapsed.get():
            self._collapsed.set(True)
            self.content.pack_forget()
            self._sync_button()

    def expand(self) -> None:
        if self._collapsed.get():
            self._collapsed.set(False)
            self.content.pack(fill="both", expand=True, pady=(6, 0))
            self._sync_button()

    @property
    def is_collapsed(self) -> bool:
        return bool(self._collapsed.get())
@dataclass(frozen=True)
class ValidationIssue:
    severity: str   # "ok" | "warn" | "error"
    scope: str      # "project" | "table" | "column" | "fk"
    table: str | None
    column: str | None
    message: str
class ValidationHeatmap(ttk.Frame):
    """
    Canvas-based heatmap:

    - rows: tables
    - cols: checks
    - cell color: ok/warn/error
    - click cell: show details
    """
    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_info: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_info = on_info

        self.canvas = tk.Canvas(self, height=220, highlightthickness=0)
        self.h = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.v = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h.set, yscrollcommand=self.v.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v.grid(row=0, column=1, sticky="ns")
        self.h.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._tables: list[str] = []
        self._checks: list[str] = []
        self._cell_details: dict[tuple[int, int], list[str]] = {}

        self._cell_w = 120
        self._cell_h = 28
        self._pad = 6

        self.canvas.bind("<Button-1>", self._on_click)

    def set_data(
        self,
        tables: list[str],
        checks: list[str],
        status: dict[tuple[str, str], str],
        details: dict[tuple[str, str], list[str]],
    ) -> None:
        """
        status[(table, check)] = "ok"|"warn"|"error"
        details[(table, check)] = list of messages
        """
        self._tables = tables
        self._checks = checks

        self._cell_details.clear()
        for ti, t in enumerate(tables):
            for ci, c in enumerate(checks):
                msgs = details.get((t, c), [])
                self._cell_details[(ti, ci)] = msgs

        self._draw(status)

    def _color(self, sev: str) -> str:
        # Keep colors subtle so text is readable
        if sev == "error":
            return "#f7b5b5"
        if sev == "warn":
            return "#ffe39a"
        return "#bfe8bf"

    def _draw(self, status: dict[tuple[str, str], str]) -> None:
        self.canvas.delete("all")

        # Header row (checks)
        x0 = self._pad + self._cell_w  # leave space for table names on left
        y0 = self._pad

        for ci, check in enumerate(self._checks):
            x = x0 + ci * self._cell_w
            self.canvas.create_rectangle(x, y0, x + self._cell_w, y0 + self._cell_h, fill="#e9e9e9", outline="#999")
            self.canvas.create_text(x + 6, y0 + self._cell_h / 2, text=check, anchor="w", font=("Segoe UI", 9, "bold"))

        # Table names + cells
        for ti, table in enumerate(self._tables):
            y = y0 + self._cell_h + ti * self._cell_h

            # table name cell
            self.canvas.create_rectangle(self._pad, y, self._pad + self._cell_w, y + self._cell_h, fill="#e9e9e9", outline="#999")
            self.canvas.create_text(self._pad + 6, y + self._cell_h / 2, text=table, anchor="w", font=("Segoe UI", 9, "bold"))

            for ci, check in enumerate(self._checks):
                x = x0 + ci * self._cell_w
                sev = status.get((table, check), "ok")
                self.canvas.create_rectangle(x, y, x + self._cell_w, y + self._cell_h, fill=self._color(sev), outline="#999")

                # Small label
                label = "OK" if sev == "ok" else ("WARN" if sev == "warn" else "ERR")
                self.canvas.create_text(x + self._cell_w / 2, y + self._cell_h / 2, text=label, font=("Segoe UI", 9))

        total_w = x0 + len(self._checks) * self._cell_w + self._pad
        total_h = y0 + (len(self._tables) + 1) * self._cell_h + self._pad
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _hit_test(self, x: int, y: int) -> tuple[int, int] | None:
        # translate x/y into table/check indices (excluding headers)
        x0 = self._pad + self._cell_w
        y0 = self._pad + self._cell_h

        if x < x0 or y < y0:
            return None

        ci = (x - x0) // self._cell_w
        ti = (y - y0) // self._cell_h

        if ti < 0 or ti >= len(self._tables):
            return None
        if ci < 0 or ci >= len(self._checks):
            return None
        return int(ti), int(ci)

    def _on_click(self, event) -> None:
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        hit = self._hit_test(x, y)
        if not hit:
            return
        ti, ci = hit
        msgs = self._cell_details.get((ti, ci), [])
        if not msgs:
            self._emit_info("Validation", "No issues.")
            return
        self._emit_info("Validation details", "\n".join(msgs))

    def _emit_info(self, title: str, message: str) -> None:
        if callable(self._on_info):
            self._on_info(title, message)
            return
        top = tk.Toplevel(self)
        top.title(title)
        top.transient(self.winfo_toplevel())
        top.geometry("520x260")
        frame = ttk.Frame(top, padding=12)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", height=10)
        text.pack(fill="both", expand=True)
        text.insert("1.0", message)
        text.configure(state="disabled")
        ttk.Button(frame, text="Close", command=top.destroy).pack(anchor="e", pady=(10, 0))

__all__ = ["ScrollableFrame", "CollapsibleSection", "ValidationIssue", "ValidationHeatmap"]
