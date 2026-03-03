"""Compatibility hub for schema-editor panel layout concerns."""

from __future__ import annotations

from src.gui.schema.editor.layout_panels_columns import build_columns_panel
from src.gui.schema.editor.layout_panels_generate import build_generate_panel
from src.gui.schema.editor.layout_panels_project import build_project_panel
from src.gui.schema.editor.layout_panels_relationships import build_relationships_panel
from src.gui.schema.editor.layout_panels_tables import build_tables_panel

__all__ = [
    "build_project_panel",
    "build_tables_panel",
    "build_columns_panel",
    "build_relationships_panel",
    "build_generate_panel",
]

