"""Token/chip-style editor for comma-separated values."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

__all__ = ["TokenEntry"]


class TokenEntry(ttk.Frame):
    """Editable token row that syncs to a comma-separated StringVar."""

    def __init__(self, parent: tk.Widget, *, textvariable: tk.StringVar) -> None:
        super().__init__(parent)
        self.textvariable = textvariable
        self._tokens: list[str] = []
        self._syncing_var = False
        self._state = "normal"

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.tokens_frame = ttk.Frame(self)
        self.tokens_frame.grid(row=0, column=0, sticky="ew")
        self.tokens_frame.columnconfigure(0, weight=1)

        self.entry_var = tk.StringVar(value="")
        self.entry = ttk.Entry(self, textvariable=self.entry_var)
        self.entry.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.entry.bind("<Return>", self._on_commit_event)
        self.entry.bind("<KP_Enter>", self._on_commit_event)
        self.entry.bind("<FocusOut>", self._on_commit_event)
        self.entry.bind(",", self._on_commit_event)

        self.textvariable.trace_add("write", self._on_external_var_changed)
        self._load_from_var()

    def configure(self, cnf=None, **kw):  # type: ignore[override]
        state = kw.pop("state", None)
        if state is not None:
            self.set_state(str(state))
        return super().configure(cnf, **kw)

    config = configure

    def set_state(self, state: str) -> None:
        new_state = "disabled" if state in {"disabled", str(tk.DISABLED)} else "normal"
        self._state = new_state
        self.entry.configure(state=new_state)
        for child in self.tokens_frame.winfo_children():
            if isinstance(child, ttk.Button):
                child.configure(state=new_state)

    def get_tokens(self) -> list[str]:
        return list(self._tokens)

    def _on_commit_event(self, _event=None):
        if self._state == "disabled":
            return "break"
        raw = self.entry_var.get().strip()
        if raw:
            for token in [part.strip() for part in raw.split(",") if part.strip()]:
                self._add_token(token)
        self.entry_var.set("")
        return "break"

    def _add_token(self, token: str) -> None:
        if token in self._tokens:
            return
        self._tokens.append(token)
        self._sync_var_from_tokens()
        self._render_tokens()

    def _remove_token(self, token: str) -> None:
        if token not in self._tokens:
            return
        self._tokens.remove(token)
        self._sync_var_from_tokens()
        self._render_tokens()

    def _render_tokens(self) -> None:
        for child in self.tokens_frame.winfo_children():
            child.destroy()

        col = 0
        for token in self._tokens:
            chip = ttk.Frame(self.tokens_frame)
            chip.grid(row=0, column=col, padx=(0, 4), pady=1, sticky="w")
            ttk.Label(chip, text=token).grid(row=0, column=0, sticky="w")
            remove = ttk.Button(chip, text="x", width=2, command=lambda t=token: self._remove_token(t))
            remove.grid(row=0, column=1, padx=(4, 0))
            if self._state == "disabled":
                remove.configure(state="disabled")
            col += 1

    def _sync_var_from_tokens(self) -> None:
        self._syncing_var = True
        self.textvariable.set(", ".join(self._tokens))
        self._syncing_var = False

    def _load_from_var(self) -> None:
        raw = self.textvariable.get().strip()
        self._tokens = []
        if raw:
            for token in [part.strip() for part in raw.split(",") if part.strip()]:
                if token not in self._tokens:
                    self._tokens.append(token)
        self._render_tokens()

    def _on_external_var_changed(self, *_args) -> None:
        if self._syncing_var:
            return
        self._load_from_var()
