"""Compatibility hub for classic schema-screen layout concerns."""

from __future__ import annotations

from src.gui.schema.classic.layout_build import _build
from src.gui.schema.classic.layout_init import __init__
from src.gui.schema.classic.layout_navigation import _browse_db_path, _on_back_requested
from src.gui.schema.classic.layout_table_selection import (
    _load_selected_table_into_editor,
    _on_table_selected,
    _refresh_tables_list,
    _set_table_editor_enabled,
)

__all__ = [
    "__init__",
    "_build",
    "_on_back_requested",
    "_set_table_editor_enabled",
    "_refresh_tables_list",
    "_on_table_selected",
    "_load_selected_table_into_editor",
    "_browse_db_path",
]

