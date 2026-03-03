"""Compatibility facade for ERD designer authoring, layout, and export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.gui.erd.authoring import (
    add_column_to_erd_project,
    add_relationship_to_erd_project,
    add_table_to_erd_project,
    new_erd_schema_project,
    update_column_in_erd_project,
    update_table_in_erd_project,
)
from src.gui.erd.common import ERD_AUTHORING_DTYPES
from src.gui.erd.layout import (
    ERDEdge,
    ERDNode,
    apply_node_position_overrides,
    build_erd_layout,
    build_table_detail_lines,
    compute_diagram_size,
    edge_label,
    node_anchor_y,
    relation_lines,
    table_for_edge,
)
from src.gui.erd.project_io import export_schema_project_to_json, load_project_schema_for_erd
from src.gui.erd.raster import (
    _export_raster_with_ghostscript_impl,
    _find_ghostscript_executable_impl,
    export_erd_file_impl,
)
from src.gui.erd.svg import build_erd_svg


def _find_ghostscript_executable() -> str | None:
    return _find_ghostscript_executable_impl()


def _export_raster_with_ghostscript(
    *,
    output_path: Path,
    postscript_data: str,
    raster_format: str,
) -> None:
    _export_raster_with_ghostscript_impl(
        output_path=output_path,
        postscript_data=postscript_data,
        raster_format=raster_format,
        finder=_find_ghostscript_executable,
    )


def export_erd_file(
    *,
    output_path_value: Any,
    svg_text: str,
    postscript_data: str | None = None,
) -> Path:
    return export_erd_file_impl(
        output_path_value=output_path_value,
        svg_text=svg_text,
        postscript_data=postscript_data,
        export_raster=_export_raster_with_ghostscript,
    )


__all__ = [
    "ERD_AUTHORING_DTYPES",
    "new_erd_schema_project",
    "add_table_to_erd_project",
    "add_column_to_erd_project",
    "add_relationship_to_erd_project",
    "update_table_in_erd_project",
    "update_column_in_erd_project",
    "export_schema_project_to_json",
    "load_project_schema_for_erd",
    "ERDNode",
    "ERDEdge",
    "build_table_detail_lines",
    "build_erd_layout",
    "edge_label",
    "node_anchor_y",
    "table_for_edge",
    "relation_lines",
    "apply_node_position_overrides",
    "compute_diagram_size",
    "build_erd_svg",
    "export_erd_file",
    "_find_ghostscript_executable",
    "_export_raster_with_ghostscript",
]
