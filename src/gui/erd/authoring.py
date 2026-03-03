"""Compatibility facade for ERD authoring helpers."""

from __future__ import annotations

from src.gui.erd.authoring_columns import add_column_to_erd_project, update_column_in_erd_project
from src.gui.erd.authoring_relationships import add_relationship_to_erd_project
from src.gui.erd.authoring_rename_refs import _replace_name_in_list, _replace_name_in_optional_value
from src.gui.erd.authoring_tables import (
    add_table_to_erd_project,
    new_erd_schema_project,
    update_table_in_erd_project,
)

__all__ = [
    "new_erd_schema_project",
    "add_table_to_erd_project",
    "add_column_to_erd_project",
    "add_relationship_to_erd_project",
    "update_table_in_erd_project",
    "update_column_in_erd_project",
    "_replace_name_in_list",
    "_replace_name_in_optional_value",
]
