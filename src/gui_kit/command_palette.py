"""Global command palette with searchable actions and dispatch."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
import tkinter as tk
from tkinter import ttk

__all__ = ["CommandPaletteAction", "CommandPaletteRegistry", "CommandPalette"]


@dataclass(frozen=True)
class CommandPaletteAction:
    """One dispatchable command entry."""

    action_id: str
    title: str
    callback: Callable[[], None]
    subtitle: str = ""
    keywords: tuple[str, ...] = ()

    def searchable_text(self) -> str:
        fields = [self.title, self.subtitle]
        fields.extend(self.keywords)
        return " ".join(_normalize_text(field) for field in fields if str(field).strip())


class CommandPaletteRegistry:
    """Action registry with deterministic fuzzy search and dispatch."""

    def __init__(self) -> None:
        self._actions: dict[str, CommandPaletteAction] = {}
        self._order: list[str] = []

    def register(self, action: CommandPaletteAction) -> None:
        action_id = _normalize_id(action.action_id)
        title = str(action.title).strip()
        if action_id == "":
            raise ValueError(
                "Command palette: action_id is required. "
                "Fix: provide a non-empty action identifier."
            )
        if title == "":
            raise ValueError(
                "Command palette: title is required. "
                "Fix: provide a non-empty action title."
            )
        if not callable(action.callback):
            raise ValueError(
                "Command palette: callback must be callable. "
                "Fix: provide a zero-argument callable callback."
            )
        if action_id in self._actions:
            raise ValueError(
                f"Command palette: duplicate action_id '{action_id}'. "
                "Fix: register each action with a unique action_id."
            )
        normalized_keywords = tuple(
            str(keyword).strip()
            for keyword in action.keywords
            if str(keyword).strip() != ""
        )
        stored = CommandPaletteAction(
            action_id=action_id,
            title=title,
            callback=action.callback,
            subtitle=str(action.subtitle).strip(),
            keywords=normalized_keywords,
        )
        self._actions[action_id] = stored
        self._order.append(action_id)

    def register_action(
        self,
        action_id: str,
        title: str,
        callback: Callable[[], None],
        *,
        subtitle: str = "",
        keywords: Iterable[str] = (),
    ) -> None:
        self.register(
            CommandPaletteAction(
                action_id=action_id,
                title=title,
                callback=callback,
                subtitle=subtitle,
                keywords=tuple(keywords),
            )
        )

    def get(self, action_id: str) -> CommandPaletteAction | None:
        return self._actions.get(_normalize_id(action_id))

    def actions(self) -> tuple[CommandPaletteAction, ...]:
        return tuple(self._actions[action_id] for action_id in self._order)

    def dispatch(self, action_id: str) -> bool:
        action = self.get(action_id)
        if action is None:
            return False
        action.callback()
        return True

    def search(self, query: str, *, limit: int = 24) -> list[CommandPaletteAction]:
        max_items = max(0, int(limit))
        if max_items == 0:
            return []

        normalized_query = _normalize_text(query)
        if normalized_query == "":
            return list(self.actions())[:max_items]

        tokens = tuple(token for token in normalized_query.split(" ") if token)
        scored: list[tuple[float, int, CommandPaletteAction]] = []
        for order_index, action_id in enumerate(self._order):
            action = self._actions[action_id]
            score = _score_action(action, normalized_query, tokens)
            if score is None:
                continue
            scored.append((score, order_index, action))
        scored.sort(key=lambda item: (-item[0], item[1], item[2].title.lower()))
        return [action for _score, _index, action in scored[:max_items]]


class CommandPalette:
    """Dialog UI for search-and-run command execution."""

    def __init__(
        self,
        widget: tk.Widget,
        *,
        registry_factory: Callable[[], CommandPaletteRegistry],
        title: str = "Command Palette",
        max_results: int = 24,
    ) -> None:
        self.widget = widget
        self._registry_factory = registry_factory
        self._title = str(title).strip() or "Command Palette"
        self._max_results = max(1, int(max_results))
        self._dialog: tk.Toplevel | None = None
        self._query_var = tk.StringVar(value="")
        self._query_trace_name: str | None = self._query_var.trace_add("write", self._on_query_changed)
        self._results_tree: ttk.Treeview | None = None
        self._status_var: tk.StringVar | None = None
        self._results: list[CommandPaletteAction] = []
        self._active_registry: CommandPaletteRegistry | None = None

    @property
    def is_open(self) -> bool:
        return self._dialog is not None and self._dialog.winfo_exists()

    @property
    def result_action_ids(self) -> tuple[str, ...]:
        return tuple(action.action_id for action in self._results)

    def open(self) -> None:
        if self.is_open:
            assert self._dialog is not None
            self._dialog.lift()
            self._dialog.focus_force()
            return

        top = tk.Toplevel(self.widget)
        self._dialog = top
        top.title(self._title)
        top.transient(self.widget.winfo_toplevel())
        top.geometry("760x360")
        top.minsize(560, 280)
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Escape>", lambda _event: self.close())
        top.bind("<Destroy>", self._on_dialog_destroy, add="+")

        body = ttk.Frame(top, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        entry = ttk.Entry(body, textvariable=self._query_var)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", self._on_activate_selected, add="+")
        entry.bind("<Down>", self._focus_results_tree, add="+")

        tree = ttk.Treeview(body, columns=("command", "context"), show="headings", height=12)
        tree.heading("command", text="Command")
        tree.heading("context", text="Context")
        tree.column("command", width=360, anchor="w")
        tree.column("context", width=300, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        tree.bind("<Return>", self._on_activate_selected, add="+")
        tree.bind("<Double-1>", self._on_activate_selected, add="+")

        scroll_y = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.grid(row=1, column=1, sticky="ns", pady=(8, 0))

        status_var = tk.StringVar(value="Type to filter commands. Enter runs selected command.")
        status = ttk.Label(body, textvariable=status_var, anchor="w")
        status.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self._results_tree = tree
        self._status_var = status_var
        self._query_var.set("")
        self._refresh_results()
        entry.focus_set()
        entry.selection_range(0, tk.END)

    def close(self) -> None:
        if not self.is_open:
            return
        assert self._dialog is not None
        self._dialog.destroy()

    def dispatch_action(self, action_id: str) -> bool:
        registry = self._registry_factory()
        dispatched = registry.dispatch(action_id)
        if dispatched:
            self.close()
        return dispatched

    def _on_dialog_destroy(self, event) -> None:
        if self._dialog is None:
            return
        if event.widget is self._dialog:
            self._dialog = None
            self._results_tree = None
            self._status_var = None
            self._results = []
            self._active_registry = None

    def _focus_results_tree(self, _event=None):
        if self._results_tree is None:
            return "break"
        self._results_tree.focus_set()
        children = self._results_tree.get_children()
        if children:
            self._results_tree.selection_set(children[0])
            self._results_tree.focus(children[0])
        return "break"

    def _on_query_changed(self, *_args) -> None:
        if not self.is_open:
            return
        self._refresh_results()

    def _refresh_results(self) -> None:
        tree = self._results_tree
        if tree is None:
            return

        registry = self._registry_factory()
        self._active_registry = registry
        query = self._query_var.get()
        self._results = registry.search(query, limit=self._max_results)

        for child_id in tree.get_children():
            tree.delete(child_id)

        if not self._results:
            if self._status_var is not None:
                self._status_var.set("No commands match the current query.")
            return

        if self._status_var is not None:
            self._status_var.set(
                f"{len(self._results)} command(s). Enter runs selected command. Esc closes palette."
            )

        for action in self._results:
            context = action.subtitle if action.subtitle else "Action"
            tree.insert("", tk.END, values=(action.title, context))
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            tree.focus(children[0])

    def _selected_action(self) -> CommandPaletteAction | None:
        tree = self._results_tree
        if tree is None:
            return None
        children = list(tree.get_children())
        if not children:
            return None

        selected = list(tree.selection())
        if selected:
            item_id = selected[0]
        else:
            item_id = children[0]
            tree.selection_set(item_id)
        try:
            index = children.index(item_id)
        except ValueError:
            return None
        if index < 0 or index >= len(self._results):
            return None
        return self._results[index]

    def _on_activate_selected(self, _event=None):
        action = self._selected_action()
        if action is None:
            return "break"
        self.close()
        action.callback()
        return "break"


def _normalize_id(value: object) -> str:
    return str(value).strip().lower()


def _normalize_text(value: object) -> str:
    text = str(value).strip().lower()
    return " ".join(text.split())


def _score_action(
    action: CommandPaletteAction,
    normalized_query: str,
    query_tokens: tuple[str, ...],
) -> float | None:
    title = _normalize_text(action.title)
    subtitle = _normalize_text(action.subtitle)
    keyword_blob = " ".join(_normalize_text(keyword) for keyword in action.keywords)
    searchable = " ".join(part for part in (title, subtitle, keyword_blob) if part)
    if searchable == "":
        return None

    if normalized_query == title:
        return 1000.0
    if title.startswith(normalized_query):
        return 930.0 - min(60.0, float(len(title) - len(normalized_query)))
    if normalized_query in title:
        return 860.0 - float(title.index(normalized_query))
    if subtitle.startswith(normalized_query):
        return 810.0
    if normalized_query in subtitle:
        return 780.0 - float(subtitle.index(normalized_query))
    if normalized_query in searchable:
        return 730.0 - float(searchable.index(normalized_query))

    if query_tokens and all(token in searchable for token in query_tokens):
        coverage = sum(len(token) for token in query_tokens)
        return 650.0 + min(120.0, float(coverage))

    ratio = SequenceMatcher(None, normalized_query, searchable).ratio()
    if ratio >= 0.58:
        return 420.0 * ratio
    return None
