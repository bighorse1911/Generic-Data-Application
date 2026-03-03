from __future__ import annotations

def _on_options_changed(self) -> None:
        if not self.show_columns_var.get() and self.show_dtypes_var.get():
            # Datatype-only rows are not meaningful without column names.
            self.show_dtypes_var.set(False)
        self._draw_erd()


def _draw_erd(self) -> None:
        self.erd_canvas.delete("all")
        if self.project is None:
            self._last_diagram_width = 1200
            self._last_diagram_height = 800
            self._node_bounds = {}
            self._node_draw_order = []
            self.erd_canvas.configure(scrollregion=(0, 0, 1200, 800))
            return

        show_columns = bool(self.show_columns_var.get())
        show_dtypes = bool(self.show_dtypes_var.get()) and show_columns

        base_nodes, edges, diagram_width, diagram_height = build_erd_layout(
            self.project,
            show_columns=show_columns,
            show_dtypes=show_dtypes,
        )
        nodes = apply_node_position_overrides(base_nodes, positions=self._node_positions)
        diagram_width, diagram_height = compute_diagram_size(
            nodes,
            min_width=diagram_width,
            min_height=diagram_height,
        )
        self._last_diagram_width = diagram_width
        self._last_diagram_height = diagram_height
        self.erd_canvas.configure(scrollregion=(0, 0, diagram_width, diagram_height))

        node_by_table = {node.table_name: node for node in nodes}
        table_map = {table.table_name: table for table in self.project.tables}
        self._node_bounds = {}
        self._node_draw_order = []

        for node in nodes:
            x1 = node.x
            y1 = node.y
            x2 = node.x + node.width
            y2 = node.y + node.height
            self._node_bounds[node.table_name] = (x1, y1, x2, y2)
            self._node_draw_order.append(node.table_name)

            self.erd_canvas.create_rectangle(x1, y1, x2, y2, fill="#ffffff", outline="#556b8a", width=2)
            self.erd_canvas.create_rectangle(x1, y1, x2, y1 + 30, fill="#dae7f8", outline="#556b8a", width=2)
            self.erd_canvas.create_text(
                x1 + 8,
                y1 + 15,
                text=node.table_name,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                fill="#1a2a44",
            )

            detail_lines = node.lines if node.lines else ["(columns hidden)"]
            y = y1 + 40
            for line in detail_lines:
                self.erd_canvas.create_text(
                    x1 + 8,
                    y,
                    text=line,
                    anchor="w",
                    font=("Consolas", 9),
                    fill="#27374d",
                )
                y += 18

        if self.show_relationships_var.get():
            for edge in edges:
                parent_node = node_by_table.get(edge.parent_table)
                child_node = node_by_table.get(edge.child_table)
                if parent_node is None or child_node is None:
                    continue
                try:
                    parent_table, child_table = table_for_edge(edge, table_map=table_map)
                except ValueError:
                    continue

                if show_columns:
                    y1 = node_anchor_y(parent_node, table=parent_table, column_name=edge.parent_column)
                    y2 = node_anchor_y(child_node, table=child_table, column_name=edge.child_column)
                else:
                    y1 = int(parent_node.y + parent_node.height / 2)
                    y2 = int(child_node.y + child_node.height / 2)
                x1 = parent_node.x + parent_node.width
                x2 = child_node.x
                mid_x = int((x1 + x2) / 2)

                self.erd_canvas.create_line(
                    x1,
                    y1,
                    mid_x,
                    y1,
                    mid_x,
                    y2,
                    x2,
                    y2,
                    fill="#1f5a95",
                    width=2,
                    arrow=tk.LAST,
                )
                self.erd_canvas.create_text(
                    mid_x + 6,
                    int((y1 + y2) / 2) - 7,
                    text=edge_label(edge),
                    anchor="w",
                    font=("Segoe UI", 8),
                    fill="#1f5a95",
                )

        self.status_var.set(
            f"Rendered ERD for project '{self.project.name}' with {len(nodes)} tables and {len(edges)} relationships."
        )
