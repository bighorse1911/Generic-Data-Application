"""Dialog for editing JSON payloads with actionable parse feedback."""

from __future__ import annotations

from collections.abc import Callable
import json
import tkinter as tk
from tkinter import ttk

__all__ = ["JsonEditorDialog", "parse_json_text"]


def parse_json_text(text: str, *, require_object: bool = False) -> tuple[object | None, str | None]:
    """Parse JSON text and return (value, error_message)."""

    candidate = text.strip()
    if candidate == "":
        candidate = "{}" if require_object else "null"

    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        location = f"line {exc.lineno}, column {exc.colno}"
        return (
            None,
            f"Params JSON editor: invalid JSON at {location}. "
            "Fix: correct JSON syntax (quotes, commas, and brackets).",
        )
    if require_object and not isinstance(value, dict):
        return (
            None,
            "Params JSON editor: JSON value must be an object. "
            "Fix: use an object like {\"key\": \"value\"}.",
        )
    return value, None


class JsonEditorDialog(tk.Toplevel):
    """Modal JSON editor with format/apply helpers."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        title: str,
        initial_text: str,
        require_object: bool,
        on_apply: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.geometry("640x420")

        self._require_object = require_object
        self._on_apply = on_apply
        self._error_var = tk.StringVar(value="")

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.text = tk.Text(body, wrap="none")
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.insert("1.0", initial_text)

        controls = ttk.Frame(body)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=0)
        controls.columnconfigure(2, weight=0)
        controls.columnconfigure(3, weight=0)

        ttk.Label(controls, textvariable=self._error_var, foreground="#aa0000").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        ttk.Button(controls, text="Format", command=self._format_json).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(controls, text="Apply", command=self._apply).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(controls, text="Cancel", command=self.destroy).grid(row=0, column=3)

    def _format_json(self) -> None:
        value, err = parse_json_text(self.text.get("1.0", "end-1c"), require_object=self._require_object)
        if err is not None:
            self._error_var.set(err)
            return
        assert value is not None
        pretty = json.dumps(value, indent=2, sort_keys=True)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", pretty)
        self._error_var.set("")

    def _apply(self) -> None:
        value, err = parse_json_text(self.text.get("1.0", "end-1c"), require_object=self._require_object)
        if err is not None:
            self._error_var.set(err)
            return
        assert value is not None
        pretty = json.dumps(value, indent=2, sort_keys=True)
        self._on_apply(pretty)
        self.destroy()
