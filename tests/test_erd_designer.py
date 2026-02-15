import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.erd_designer import (
    ERDEdge,
    add_column_to_erd_project,
    add_relationship_to_erd_project,
    add_table_to_erd_project,
    apply_node_position_overrides,
    build_erd_layout,
    build_erd_svg,
    build_table_detail_lines,
    compute_diagram_size,
    edge_label,
    export_schema_project_to_json,
    export_erd_file,
    load_project_schema_for_erd,
    new_erd_schema_project,
    table_for_edge,
    update_column_in_erd_project,
    update_table_in_erd_project,
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

    def test_new_erd_schema_project_requires_name_and_integer_seed(self):
        project = new_erd_schema_project(name_value=" draft_schema ", seed_value="42")
        self.assertEqual(project.name, "draft_schema")
        self.assertEqual(project.seed, 42)
        self.assertEqual(project.tables, [])
        self.assertEqual(project.foreign_keys, [])

        with self.assertRaises(ValueError) as name_ctx:
            new_erd_schema_project(name_value="", seed_value=1)
        self.assertIn("ERD Designer / Schema name", str(name_ctx.exception))
        self.assertIn("Fix:", str(name_ctx.exception))

        with self.assertRaises(ValueError) as seed_ctx:
            new_erd_schema_project(name_value="ok", seed_value="not_a_seed")
        self.assertIn("ERD Designer / Schema seed", str(seed_ctx.exception))
        self.assertIn("Fix:", str(seed_ctx.exception))

    def test_add_table_to_erd_project_adds_unique_table(self):
        project = new_erd_schema_project(name_value="demo", seed_value=123)
        updated = add_table_to_erd_project(project, table_name_value="customers", row_count_value="25")
        self.assertEqual(len(updated.tables), 1)
        self.assertEqual(updated.tables[0].table_name, "customers")
        self.assertEqual(updated.tables[0].row_count, 25)

        with self.assertRaises(ValueError) as ctx:
            add_table_to_erd_project(updated, table_name_value="customers", row_count_value=10)
        self.assertIn("ERD Designer / Add table / Name", str(ctx.exception))
        self.assertIn("Fix:", str(ctx.exception))

    def test_add_column_to_erd_project_enforces_dtype_and_pk_rules(self):
        project = new_erd_schema_project(name_value="demo", seed_value=1)
        project = add_table_to_erd_project(project, table_name_value="customers")
        project = add_column_to_erd_project(
            project,
            table_name_value="customers",
            column_name_value="customer_id",
            dtype_value="int",
            primary_key=True,
            nullable=True,
        )
        self.assertEqual(project.tables[0].columns[0].name, "customer_id")
        self.assertTrue(project.tables[0].columns[0].primary_key)
        self.assertFalse(project.tables[0].columns[0].nullable)

        with self.assertRaises(ValueError) as float_ctx:
            add_column_to_erd_project(
                project,
                table_name_value="customers",
                column_name_value="amount",
                dtype_value="float",
                primary_key=False,
                nullable=True,
            )
        self.assertIn("ERD Designer / Add column / DType", str(float_ctx.exception))
        self.assertIn("Fix:", str(float_ctx.exception))

        with self.assertRaises(ValueError) as second_pk_ctx:
            add_column_to_erd_project(
                project,
                table_name_value="customers",
                column_name_value="other_id",
                dtype_value="int",
                primary_key=True,
                nullable=False,
            )
        self.assertIn("ERD Designer / Add column / Primary key", str(second_pk_ctx.exception))
        self.assertIn("Fix:", str(second_pk_ctx.exception))

    def test_add_relationship_to_erd_project_adds_fk_and_rejects_invalid(self):
        project = new_erd_schema_project(name_value="demo", seed_value=1)
        project = add_table_to_erd_project(project, table_name_value="customers")
        project = add_table_to_erd_project(project, table_name_value="orders")
        project = add_column_to_erd_project(
            project,
            table_name_value="customers",
            column_name_value="customer_id",
            dtype_value="int",
            primary_key=True,
            nullable=False,
        )
        project = add_column_to_erd_project(
            project,
            table_name_value="orders",
            column_name_value="order_id",
            dtype_value="int",
            primary_key=True,
            nullable=False,
        )
        project = add_column_to_erd_project(
            project,
            table_name_value="orders",
            column_name_value="customer_id",
            dtype_value="int",
            primary_key=False,
            nullable=False,
        )
        project = add_relationship_to_erd_project(
            project,
            child_table_value="orders",
            child_column_value="customer_id",
            parent_table_value="customers",
            parent_column_value="customer_id",
            min_children_value=1,
            max_children_value=4,
        )
        self.assertEqual(len(project.foreign_keys), 1)
        self.assertEqual(project.foreign_keys[0].child_table, "orders")

        with self.assertRaises(ValueError) as duplicate_ctx:
            add_relationship_to_erd_project(
                project,
                child_table_value="orders",
                child_column_value="customer_id",
                parent_table_value="customers",
                parent_column_value="customer_id",
            )
        self.assertIn("ERD Designer / Add relationship", str(duplicate_ctx.exception))
        self.assertIn("Fix:", str(duplicate_ctx.exception))

        invalid_project = add_column_to_erd_project(
            project,
            table_name_value="orders",
            column_name_value="bad_parent_ref",
            dtype_value="text",
            primary_key=False,
            nullable=True,
        )
        with self.assertRaises(ValueError) as bad_dtype_ctx:
            add_relationship_to_erd_project(
                invalid_project,
                child_table_value="orders",
                child_column_value="bad_parent_ref",
                parent_table_value="customers",
                parent_column_value="customer_id",
            )
        self.assertIn("ERD Designer / Add relationship / Child column", str(bad_dtype_ctx.exception))
        self.assertIn("Fix:", str(bad_dtype_ctx.exception))

    def test_update_table_in_erd_project_renames_table_and_updates_fks(self):
        project = update_table_in_erd_project(
            self._project(),
            current_table_name_value="customers",
            new_table_name_value="clients",
            row_count_value="12",
        )
        table_names = [table.table_name for table in project.tables]
        self.assertIn("clients", table_names)
        self.assertNotIn("customers", table_names)
        clients = next(table for table in project.tables if table.table_name == "clients")
        self.assertEqual(clients.row_count, 12)
        self.assertEqual(project.foreign_keys[0].parent_table, "clients")

    def test_update_column_in_erd_project_updates_relationship_references(self):
        project = update_column_in_erd_project(
            self._project(),
            table_name_value="customers",
            current_column_name_value="customer_id",
            new_column_name_value="client_id",
            dtype_value="int",
            primary_key=True,
            nullable=False,
        )
        customers = next(table for table in project.tables if table.table_name == "customers")
        self.assertEqual(customers.columns[0].name, "client_id")
        self.assertTrue(customers.columns[0].primary_key)
        self.assertEqual(project.foreign_keys[0].parent_column, "client_id")

    def test_update_column_in_erd_project_rejects_dropping_referenced_parent_pk(self):
        with self.assertRaises(ValueError) as ctx:
            update_column_in_erd_project(
                self._project(),
                table_name_value="customers",
                current_column_name_value="customer_id",
                new_column_name_value="customer_id",
                dtype_value="int",
                primary_key=False,
                nullable=False,
            )
        msg = str(ctx.exception)
        self.assertIn("ERD Designer / Edit column / Primary key", msg)
        self.assertIn("Fix:", msg)

    def test_export_schema_project_to_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "erd_schema.json"
            saved = export_schema_project_to_json(
                project=self._project(),
                output_path_value=str(output_path),
            )
            self.assertEqual(saved, output_path)
            self.assertTrue(output_path.exists())
            loaded = load_project_schema_for_erd(str(output_path))
            self.assertEqual(loaded.name, "erd_demo")

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
