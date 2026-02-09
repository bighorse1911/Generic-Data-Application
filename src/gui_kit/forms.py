"""Form construction helpers for consistent labeled input rows."""

from functools import partial
import tkinter as tk
from tkinter import ttk

__all__ = ["FormBuilder"]


class FormBuilder:
    """
    Consistent label+control form rows on a grid.

    - Column 0: labels
    - Column 1: controls (stretch)
    """

    def __init__(self, container: ttk.Frame) -> None:
        self.container = container
        self._row = 0

        self.container.columnconfigure(0, weight=0)
        self.container.columnconfigure(1, weight=1)

    def add_entry(
        self,
        label: str,
        textvariable: tk.StringVar,
        width: int | None = None,
    ) -> ttk.Entry:
        """Add an Entry row bound to a StringVar."""

        entry = ttk.Entry(self.container, textvariable=textvariable, width=width)
        self._add_labeled_control(label, entry)
        return entry

    def add_combo(
        self,
        label: str,
        textvariable: tk.StringVar,
        values: list[str],
        readonly: bool = True,
    ) -> ttk.Combobox:
        """Add a Combobox row with optional readonly mode."""

        state = "readonly" if readonly else "normal"
        combo = ttk.Combobox(self.container, textvariable=textvariable, values=values, state=state)
        self._add_labeled_control(label, combo)
        return combo

    def add_check(self, label: str, variable: tk.Variable) -> ttk.Checkbutton:
        """Add a Checkbutton row."""

        check = ttk.Checkbutton(self.container, variable=variable)
        self._add_labeled_control(label, check)
        return check

    def add_text(
        self,
        label: str,
        value_or_widget: tk.StringVar | tk.Text | None = None,
        *,
        height: int = 4,
    ) -> tk.Text:
        """Add a multi-line Text row and optionally sync it to a StringVar."""

        if isinstance(value_or_widget, tk.Text):
            text = value_or_widget
        else:
            text = tk.Text(self.container, height=height, wrap="word")
            if isinstance(value_or_widget, tk.StringVar):
                text.insert("1.0", value_or_widget.get())
                text.bind(
                    "<KeyRelease>",
                    partial(self._copy_text_to_variable, widget=text, variable=value_or_widget),
                )
        self._add_labeled_control(label, text, sticky="nsew")
        return text

    def _add_labeled_control(self, label: str, widget: tk.Widget, *, sticky: str = "ew") -> None:
        """Add the standard label+widget pair at the next available row."""

        row = self._row
        ttk.Label(self.container, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        widget.grid(row=row, column=1, sticky=sticky, pady=4)
        self._row += 1

    @staticmethod
    def _copy_text_to_variable(_event, *, widget: tk.Text, variable: tk.StringVar) -> None:
        """Sync current Text content to the bound StringVar."""

        variable.set(widget.get("1.0", "end-1c"))
