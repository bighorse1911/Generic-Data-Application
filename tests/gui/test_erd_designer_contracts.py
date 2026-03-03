from __future__ import annotations

import unittest
from unittest import mock

import src.erd_designer as erd


class ERDDesignerContractsTests(unittest.TestCase):
    def test_facade_symbol_surface(self) -> None:
        required = (
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
        )
        for name in required:
            self.assertTrue(hasattr(erd, name), f"Missing src.erd_designer symbol: {name}")

    def test_export_erd_file_uses_patchable_ghostscript_finder(self) -> None:
        with mock.patch("src.erd_designer._find_ghostscript_executable", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                erd.export_erd_file(
                    output_path_value="diagram.png",
                    svg_text="<svg></svg>",
                    postscript_data="%!PS-Adobe-3.0",
                )

        msg = str(ctx.exception)
        self.assertIn("ERD Designer / Export", msg)
        self.assertIn("Ghostscript", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
