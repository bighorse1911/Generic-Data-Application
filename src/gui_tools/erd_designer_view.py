import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.erd_designer import (
    ERD_AUTHORING_DTYPES,
    add_column_to_erd_project,
    add_relationship_to_erd_project,
    add_table_to_erd_project,
    apply_node_position_overrides,
    build_erd_layout,
    build_erd_svg,
    compute_diagram_size,
    edge_label,
    export_schema_project_to_json,
    export_erd_file,
    load_project_schema_for_erd,
    new_erd_schema_project,
    node_anchor_y,
    table_for_edge,
    update_column_in_erd_project,
    update_table_in_erd_project,
)
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog


from src.gui_tools.erd_designer import authoring_actions as erd_authoring_actions
from src.gui_tools.erd_designer import authoring_sync as erd_authoring_sync
from src.gui_tools.erd_designer import build as erd_build
from src.gui_tools.erd_designer import dragging as erd_dragging
from src.gui_tools.erd_designer import helpers as erd_helpers
from src.gui_tools.erd_designer import io_export as erd_io_export
from src.gui_tools.erd_designer import rendering as erd_rendering


def _bind_erd_tool_module_context(module) -> None:
    for name, value in globals().items():
        if name.startswith('__'):
            continue
        module.__dict__.setdefault(name, value)


class ERDDesignerToolFrame(ttk.Frame):
    """Schema-to-diagram view for table/column/FK relationship inspection."""

    ERROR_SURFACE_CONTEXT = "ERD designer"
    ERROR_DIALOG_TITLE = "ERD designer error"
    WARNING_DIALOG_TITLE = "ERD designer warning"

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig, *, show_header: bool=True, title_text: str='ERD Designer') -> None:
        return erd_build.__init__(self, parent, app, cfg, show_header=show_header, title_text=title_text)


    def _erd_error(self, field: str, issue: str, hint: str) -> str:
        return erd_helpers._erd_error(self, field, issue, hint)


    def _show_error_dialog(self, location: str, message: object) -> str:
        return erd_helpers._show_error_dialog(self, location, message)


    def _browse_schema_path(self) -> None:
        return erd_io_export._browse_schema_path(self)


    def _toggle_authoring_panel(self) -> None:
        return erd_authoring_sync._toggle_authoring_panel(self)


    def _set_combo_values(self, combo: ttk.Combobox, *, values: list[str], variable: tk.StringVar) -> None:
        return erd_helpers._set_combo_values(self, combo, values=values, variable=variable)


    def _table_names(self) -> list[str]:
        return erd_helpers._table_names(self)


    def _table_for_name(self, table_name: str) -> object | None:
        return erd_helpers._table_for_name(self, table_name)


    def _columns_for_table(self, table_name: str, *, primary_key_only: bool=False) -> list[str]:
        return erd_helpers._columns_for_table(self, table_name, primary_key_only=primary_key_only)


    def _sync_authoring_controls_from_project(self) -> None:
        return erd_authoring_sync._sync_authoring_controls_from_project(self)


    def _on_column_pk_changed(self) -> None:
        return erd_authoring_sync._on_column_pk_changed(self)


    def _on_column_table_changed(self) -> None:
        return erd_authoring_sync._on_column_table_changed(self)


    def _on_edit_table_selected(self) -> None:
        return erd_authoring_sync._on_edit_table_selected(self)


    def _on_edit_column_table_changed(self) -> None:
        return erd_authoring_sync._on_edit_column_table_changed(self)


    def _on_edit_column_selected(self) -> None:
        return erd_authoring_sync._on_edit_column_selected(self)


    def _on_edit_column_pk_changed(self) -> None:
        return erd_authoring_sync._on_edit_column_pk_changed(self)


    def _reset_table_editor(self) -> None:
        return erd_authoring_sync._reset_table_editor(self)


    def _reset_column_editor(self) -> None:
        return erd_authoring_sync._reset_column_editor(self)


    def _save_table_shared(self) -> None:
        return erd_authoring_sync._save_table_shared(self)


    def _save_column_shared(self) -> None:
        return erd_authoring_sync._save_column_shared(self)


    def _on_relationship_child_table_changed(self) -> None:
        return erd_authoring_sync._on_relationship_child_table_changed(self)


    def _on_relationship_parent_table_changed(self) -> None:
        return erd_authoring_sync._on_relationship_parent_table_changed(self)


    def _create_new_schema(self) -> None:
        return erd_authoring_actions._create_new_schema(self)


    def _add_table(self) -> None:
        return erd_authoring_actions._add_table(self)


    def _edit_table(self) -> None:
        return erd_authoring_actions._edit_table(self)


    def _add_column(self) -> None:
        return erd_authoring_actions._add_column(self)


    def _edit_column(self) -> None:
        return erd_authoring_actions._edit_column(self)


    def _add_relationship(self) -> None:
        return erd_authoring_actions._add_relationship(self)


    def _load_and_render(self) -> None:
        return erd_io_export._load_and_render(self)


    def _export_schema_json(self) -> None:
        return erd_io_export._export_schema_json(self)


    def _export_erd(self) -> None:
        return erd_io_export._export_erd(self)


    def _on_options_changed(self) -> None:
        return erd_rendering._on_options_changed(self)


    def _draw_erd(self) -> None:
        return erd_rendering._draw_erd(self)


    def _table_name_at_canvas_point(self, x: float, y: float) -> str | None:
        return erd_dragging._table_name_at_canvas_point(self, x, y)


    def _on_erd_drag_start(self, event: tk.Event) -> None:
        return erd_dragging._on_erd_drag_start(self, event)


    def _on_erd_drag_motion(self, event: tk.Event) -> None:
        return erd_dragging._on_erd_drag_motion(self, event)


    def _on_erd_drag_end(self, _event: tk.Event) -> None:
        return erd_dragging._on_erd_drag_end(self, _event)


for _erd_module in (
    erd_build,
    erd_helpers,
    erd_authoring_sync,
    erd_authoring_actions,
    erd_io_export,
    erd_rendering,
    erd_dragging,
):
    _bind_erd_tool_module_context(_erd_module)


__all__ = ["ERDDesignerToolFrame"]
