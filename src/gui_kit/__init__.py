"""Public gui_kit API and machine-readable component catalog.

The catalog gives tools a stable way to discover reusable gui_kit components
without scraping module internals.
"""

from __future__ import annotations

from typing import TypedDict

from src.gui_kit.command_palette import CommandPalette, CommandPaletteAction, CommandPaletteRegistry
from src.gui_kit.column_chooser import ColumnChooserDialog
from src.gui_kit.forms import FormBuilder
from src.gui_kit.feedback import NotificationCenter, NotificationEntry, ToastCenter
from src.gui_kit.json_editor import JsonEditorDialog, parse_json_text
from src.gui_kit.layout import BaseScreen
from src.gui_kit.panels import CollapsiblePanel, Tabs
from src.gui_kit.preferences import WorkspacePreferencesStore, default_workspace_preferences_path
from src.gui_kit.search import SearchEntry
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.scroll import ScrollFrame, wheel_units_from_delta
from src.gui_kit.table import TableView
from src.gui_kit.theme_tokens import V2_THEME, v2_button_options
from src.gui_kit.tokens import TokenEntry
from src.gui_kit.validation import InlineValidationEntry, InlineValidationSummary


class GUIKitComponent(TypedDict):
    """Machine-readable descriptor for one public gui_kit component."""

    export: str
    module: str
    kind: str
    summary: str

__all__ = [
    "BaseScreen",
    "CommandPalette",
    "CommandPaletteAction",
    "CommandPaletteRegistry",
    "CollapsiblePanel",
    "ColumnChooserDialog",
    "FormBuilder",
    "InlineValidationEntry",
    "InlineValidationSummary",
    "JsonEditorDialog",
    "GUIKitComponent",
    "NotificationCenter",
    "NotificationEntry",
    "WorkspacePreferencesStore",
    "default_workspace_preferences_path",
    "SearchEntry",
    "ShortcutManager",
    "ScrollFrame",
    "TableView",
    "V2_THEME",
    "ToastCenter",
    "TokenEntry",
    "Tabs",
    "get_component_catalog",
    "parse_json_text",
    "v2_button_options",
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
        "export": "CommandPalette",
        "module": "src.gui_kit.command_palette",
        "kind": "command_palette",
        "summary": "Global searchable action launcher dialog with keyboard-first dispatch.",
    },
    {
        "export": "CommandPaletteAction",
        "module": "src.gui_kit.command_palette",
        "kind": "command_palette_model",
        "summary": "Dataclass model describing one command-palette action entry.",
    },
    {
        "export": "CommandPaletteRegistry",
        "module": "src.gui_kit.command_palette",
        "kind": "command_palette_registry",
        "summary": "Action registry with deterministic fuzzy search and dispatch helpers.",
    },
    {
        "export": "ColumnChooserDialog",
        "module": "src.gui_kit.column_chooser",
        "kind": "dialog",
        "summary": "Modal chooser for visible-column selection and display order.",
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
        "export": "ToastCenter",
        "module": "src.gui_kit.feedback",
        "kind": "feedback",
        "summary": "Non-blocking stacked toasts for success/warn/error status messages.",
    },
    {
        "export": "NotificationCenter",
        "module": "src.gui_kit.feedback",
        "kind": "notification_center",
        "summary": "Non-blocking notifications with in-memory history and history dialog.",
    },
    {
        "export": "NotificationEntry",
        "module": "src.gui_kit.feedback",
        "kind": "notification_model",
        "summary": "Dataclass payload for one notification history entry.",
    },
    {
        "export": "WorkspacePreferencesStore",
        "module": "src.gui_kit.preferences",
        "kind": "preferences_store",
        "summary": "Versioned route-keyed workspace state persistence store.",
    },
    {
        "export": "default_workspace_preferences_path",
        "module": "src.gui_kit.preferences",
        "kind": "preferences_helper",
        "summary": "Returns default workspace-state file path with env override support.",
    },
    {
        "export": "SearchEntry",
        "module": "src.gui_kit.search",
        "kind": "search",
        "summary": "Debounced search entry with deterministic delay and clear action.",
    },
    {
        "export": "TokenEntry",
        "module": "src.gui_kit.tokens",
        "kind": "token_editor",
        "summary": "Chip-style editor synchronized to comma-separated StringVar values.",
    },
    {
        "export": "JsonEditorDialog",
        "module": "src.gui_kit.json_editor",
        "kind": "json_editor",
        "summary": "Modal JSON editor with pretty-format and actionable parse errors.",
    },
    {
        "export": "parse_json_text",
        "module": "src.gui_kit.json_editor",
        "kind": "json_helper",
        "summary": "JSON parse helper returning actionable error text with line/column hints.",
    },
    {
        "export": "ShortcutManager",
        "module": "src.gui_kit.shortcuts",
        "kind": "shortcuts",
        "summary": "Centralized keyboard shortcut manager with discoverable help dialog.",
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
        "summary": "Treeview wrapper with normalization, auto-sizing, and optional pagination.",
    },
    {
        "export": "V2_THEME",
        "module": "src.gui_kit.theme_tokens",
        "kind": "theme_tokens",
        "summary": "Shared v2 visual token set (colors, typography, spacing, focus, button hierarchy).",
    },
    {
        "export": "InlineValidationEntry",
        "module": "src.gui_kit.validation",
        "kind": "validation_model",
        "summary": "Dataclass payload model for inline validation rows.",
    },
    {
        "export": "InlineValidationSummary",
        "module": "src.gui_kit.validation",
        "kind": "validation_panel",
        "summary": "Inline validation list with quick-jump callback support.",
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
    {
        "export": "v2_button_options",
        "module": "src.gui_kit.theme_tokens",
        "kind": "theme_helper",
        "summary": "Returns tokenized tk.Button visual options by hierarchy role.",
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
