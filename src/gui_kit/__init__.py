"""Public gui_kit API and machine-readable component catalog.

The catalog gives tools a stable way to discover reusable gui_kit components
without scraping module internals.
"""

from __future__ import annotations

from typing import TypedDict

from src.gui_kit.forms import FormBuilder
from src.gui_kit.layout import BaseScreen
from src.gui_kit.panels import CollapsiblePanel, Tabs
from src.gui_kit.scroll import ScrollFrame, wheel_units_from_delta
from src.gui_kit.table import TableView


class GUIKitComponent(TypedDict):
    """Machine-readable descriptor for one public gui_kit component."""

    export: str
    module: str
    kind: str
    summary: str

__all__ = [
    "BaseScreen",
    "CollapsiblePanel",
    "FormBuilder",
    "GUIKitComponent",
    "ScrollFrame",
    "TableView",
    "Tabs",
    "get_component_catalog",
    "wheel_units_from_delta",
]

_COMPONENT_CATALOG: tuple[GUIKitComponent, ...] = (
    {
        "export": "BaseScreen",
        "module": "src.gui_kit.layout",
        "kind": "screen_base",
        "summary": "Base class with shared status/busy/thread helpers for screens.",
    },
    {
        "export": "CollapsiblePanel",
        "module": "src.gui_kit.panels",
        "kind": "layout_panel",
        "summary": "Expandable/collapsible section for large forms.",
    },
    {
        "export": "FormBuilder",
        "module": "src.gui_kit.forms",
        "kind": "form_builder",
        "summary": "Grid-based helper for labeled Tk controls.",
    },
    {
        "export": "ScrollFrame",
        "module": "src.gui_kit.scroll",
        "kind": "scroll_container",
        "summary": "Canvas-backed frame with 2-axis scrolling and wheel support.",
    },
    {
        "export": "TableView",
        "module": "src.gui_kit.table",
        "kind": "table_widget",
        "summary": "Treeview wrapper with normalization and auto-sizing helpers.",
    },
    {
        "export": "Tabs",
        "module": "src.gui_kit.panels",
        "kind": "tab_container",
        "summary": "Notebook wrapper with add_tab convenience API.",
    },
    {
        "export": "wheel_units_from_delta",
        "module": "src.gui_kit.scroll",
        "kind": "scroll_helper",
        "summary": "Normalizes raw mouse-wheel delta values to Tk scroll units.",
    },
)


def get_component_catalog() -> tuple[GUIKitComponent, ...]:
    """Return stable gui_kit component metadata for tools and docs."""

    return _COMPONENT_CATALOG


def _validate_component_catalog() -> None:
    required_keys = ("export", "module", "kind", "summary")
    for index, component in enumerate(_COMPONENT_CATALOG, start=1):
        for key in required_keys:
            value = component.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Invalid gui_kit catalog entry #{index}: field '{key}' is missing or blank. "
                    "Fix: provide a non-empty string for each catalog field."
                )

        export = component["export"]
        module = component["module"]
        if export not in __all__:
            raise ValueError(
                f"Invalid gui_kit catalog entry #{index}: export '{export}' is not listed in __all__. "
                "Fix: add the symbol to __all__ or correct the catalog entry."
            )

        if export not in globals():
            raise ValueError(
                f"Invalid gui_kit catalog entry #{index}: export '{export}' is not imported in src.gui_kit.__init__. "
                "Fix: import the symbol before validating the catalog."
            )

        if not module.startswith("src.gui_kit."):
            raise ValueError(
                f"Invalid gui_kit catalog entry #{index}: module '{module}' must start with 'src.gui_kit.'. "
                "Fix: point the entry to the canonical gui_kit module path."
            )


_validate_component_catalog()
