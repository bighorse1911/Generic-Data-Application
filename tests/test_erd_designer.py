import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.erd_designer import (
    ERDEdge,
    apply_node_position_overrides,
    build_erd_layout,
    build_erd_svg,
    build_table_detail_lines,
    compute_diagram_size,
    edge_label,
    export_erd_file,
    load_project_schema_for_erd,
    table_for_edge,
)
from src.schema_project_io import save_project_to_json
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


class TestERDDesigner(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="erd_demo",
            seed=7,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=5,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("name", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    row_count=10,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("amount", "decimal", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("orders", "customer_id", "customers", "customer_id", 1, 3),
            ],
        )

    def test_load_project_schema_for_erd_requires_existing_path(self):
        with self.assertRaises(ValueError) as ctx:
            load_project_schema_for_erd("this_file_should_not_exist_123456.json")
        msg = str(ctx.exception)
        self.assertIn("ERD Designer / Schema path", msg)
        self.assertIn("Fix:", msg)

    def test_load_project_schema_for_erd_roundtrip(self):
        project = self._project()
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            loaded = load_project_schema_for_erd(path)
            self.assertEqual(loaded.name, project.name)
            self.assertEqual(len(loaded.tables), 2)
            self.assertEqual(len(loaded.foreign_keys), 1)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_build_table_detail_lines_respects_options(self):
        table = self._project().tables[1]

        visible = build_table_detail_lines(
            table,
            fk_columns={"customer_id"},
            show_columns=True,
            show_dtypes=True,
        )
        self.assertIn("[PK] order_id: int", visible)
        self.assertIn("[FK] customer_id: int", visible)
        self.assertIn("amount: decimal", visible)

        names_only = build_table_detail_lines(
            table,
            fk_columns={"customer_id"},
            show_columns=True,
            show_dtypes=False,
        )
        self.assertIn("[PK] order_id", names_only)
        self.assertNotIn("[PK] order_id: int", names_only)

        hidden = build_table_detail_lines(
            table,
            fk_columns={"customer_id"},
            show_columns=False,
            show_dtypes=False,
        )
        self.assertEqual(hidden, [])

    def test_build_erd_layout_is_deterministic_and_contains_edges(self):
        project = self._project()
        a = build_erd_layout(project, show_columns=True, show_dtypes=True)
        b = build_erd_layout(project, show_columns=True, show_dtypes=True)
        self.assertEqual(a, b)

        nodes, edges, width, height = a
        self.assertEqual(len(nodes), 2)
        self.assertEqual(len(edges), 1)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        self.assertEqual(edge_label(edges[0]), "orders.customer_id -> customers.customer_id")

    def test_apply_node_position_overrides_updates_selected_tables(self):
        nodes, _edges, _width, _height = build_erd_layout(self._project(), show_columns=True, show_dtypes=True)
        moved = apply_node_position_overrides(
            nodes,
            positions={"customers": (500, 420)},
        )
        moved_by_name = {node.table_name: node for node in moved}
        self.assertEqual(moved_by_name["customers"].x, 500)
        self.assertEqual(moved_by_name["customers"].y, 420)

        original_by_name = {node.table_name: node for node in nodes}
        self.assertEqual(moved_by_name["orders"].x, original_by_name["orders"].x)
        self.assertEqual(moved_by_name["orders"].y, original_by_name["orders"].y)

    def test_compute_diagram_size_expands_for_moved_nodes(self):
        nodes, _edges, width, height = build_erd_layout(self._project(), show_columns=True, show_dtypes=True)
        moved = apply_node_position_overrides(nodes, positions={"customers": (1200, 700)})
        out_width, out_height = compute_diagram_size(moved, min_width=width, min_height=height)
        self.assertGreaterEqual(out_width, 1200 + moved[0].width + 32)
        self.assertGreaterEqual(out_height, 700 + moved[0].height + 32)

    def test_build_erd_svg_contains_tables_and_relationship_label(self):
        svg = build_erd_svg(
            self._project(),
            show_relationships=True,
            show_columns=True,
            show_dtypes=True,
        )
        self.assertIn("<svg", svg)
        self.assertIn("customers", svg)
        self.assertIn("orders.customer_id -&gt; customers.customer_id", svg)

    def test_build_erd_svg_respects_node_position_overrides(self):
        svg = build_erd_svg(
            self._project(),
            show_relationships=True,
            show_columns=True,
            show_dtypes=True,
            node_positions={"customers": (500, 420)},
        )
        self.assertIn('x="500" y="420"', svg)

    def test_export_erd_file_writes_svg(self):
        svg = build_erd_svg(
            self._project(),
            show_relationships=True,
            show_columns=True,
            show_dtypes=True,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "diagram.svg"
            saved = export_erd_file(output_path_value=str(output_path), svg_text=svg)
            self.assertEqual(saved, output_path)
            self.assertTrue(output_path.exists())
            written = output_path.read_text(encoding="utf-8")
            self.assertIn("<svg", written)

    def test_export_erd_file_rejects_unknown_extension(self):
        with self.assertRaises(ValueError) as ctx:
            export_erd_file(output_path_value="diagram.txt", svg_text="<svg />")
        msg = str(ctx.exception)
        self.assertIn("ERD Designer / Export format", msg)
        self.assertIn("Fix:", msg)

    def test_export_erd_file_png_requires_ghostscript(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "diagram.png"
            with mock.patch("src.erd_designer._find_ghostscript_executable", return_value=None):
                with self.assertRaises(ValueError) as ctx:
                    export_erd_file(
                        output_path_value=str(output_path),
                        svg_text="<svg />",
                        postscript_data="%!PS-Adobe-3.0\nshowpage\n",
                    )
        msg = str(ctx.exception)
        self.assertIn("ERD Designer / Export", msg)
        self.assertIn("Ghostscript", msg)
        self.assertIn("Fix:", msg)

    def test_table_for_edge_reports_unknown_tables_actionably(self):
        edge = ERDEdge(
            parent_table="missing_parent",
            parent_column="id",
            child_table="orders",
            child_column="customer_id",
        )
        with self.assertRaises(ValueError) as ctx:
            table_for_edge(edge, table_map={"orders": self._project().tables[1]})
        msg = str(ctx.exception)
        self.assertIn("ERD Designer / Relationships", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
