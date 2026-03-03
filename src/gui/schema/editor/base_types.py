from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.schema_project_model import SchemaProject


VALIDATION_DEBOUNCE_MS = 180
FILTER_PAGE_SIZE = 200
UNDO_STACK_LIMIT = 120
STARTER_FIXTURE_PATH = Path("tests/fixtures/default_schema_project.json")


@dataclass(frozen=True)
class IndexedFilterRow:
    source_index: int
    values: tuple[object, ...]
    search_text: str


@dataclass(frozen=True)
class EditorUndoSnapshot:
    project: SchemaProject
    selected_table_index: int | None
    selected_column_index: int | None
    selected_fk_index: int | None


__all__ = [
    "VALIDATION_DEBOUNCE_MS",
    "FILTER_PAGE_SIZE",
    "UNDO_STACK_LIMIT",
    "STARTER_FIXTURE_PATH",
    "IndexedFilterRow",
    "EditorUndoSnapshot",
]
