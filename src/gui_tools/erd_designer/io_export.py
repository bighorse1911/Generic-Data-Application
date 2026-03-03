from __future__ import annotations

def _browse_schema_path(self) -> None:
        path = filedialog.askopenfilename(
            title="Select schema project JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path == "":
            return
        self.schema_path_var.set(path)


def _load_and_render(self) -> None:
        try:
            self.project = load_project_schema_for_erd(self.schema_path_var.get())
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        self.schema_name_var.set(self.project.name)
        self.schema_seed_var.set(str(self.project.seed))
        self._node_positions = {}
        self._node_bounds = {}
        self._node_draw_order = []
        self._drag_table_name = None
        self._drag_offset = None
        self._sync_authoring_controls_from_project()
        self._draw_erd()


def _export_schema_json(self) -> None:
        if self.project is None:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Schema export",
                    "schema is not loaded",
                    "create or load a schema project before exporting JSON",
                ),
            )
            return

        output_path = filedialog.asksaveasfilename(
            title="Export schema project JSON",
            defaultextension=".json",
            initialfile=f"{self.project.name}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.status_var.set("Schema JSON export cancelled.")
            return

        try:
            saved_path = export_schema_project_to_json(
                project=self.project,
                output_path_value=output_path,
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return

        self.schema_path_var.set(str(saved_path))
        self.status_var.set(f"Exported schema JSON to {saved_path}.")


def _export_erd(self) -> None:
        if self.project is None:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    "ERD is not loaded",
                    "load and render a schema project before exporting",
                ),
            )
            return

        output_path = filedialog.asksaveasfilename(
            title="Export ERD",
            defaultextension=".svg",
            initialfile=f"{self.project.name}_erd.svg",
            filetypes=[
                ("SVG files", "*.svg"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
        )
        if output_path == "":
            self.status_var.set("ERD export cancelled.")
            return

        show_columns = bool(self.show_columns_var.get())
        show_dtypes = bool(self.show_dtypes_var.get()) and show_columns
        ext = Path(output_path).suffix.lower()
        postscript_data: str | None = None

        try:
            svg_text = build_erd_svg(
                self.project,
                show_relationships=bool(self.show_relationships_var.get()),
                show_columns=show_columns,
                show_dtypes=show_dtypes,
                node_positions=self._node_positions,
            )
            if ext in {".png", ".jpg", ".jpeg"}:
                width = max(1, int(self._last_diagram_width))
                height = max(1, int(self._last_diagram_height))
                postscript_data = self.erd_canvas.postscript(
                    colormode="color",
                    x=0,
                    y=0,
                    width=width,
                    height=height,
                    pagewidth=f"{width}p",
                    pageheight=f"{height}p",
                )
            saved_path = export_erd_file(
                output_path_value=output_path,
                svg_text=svg_text,
                postscript_data=postscript_data,
            )
        except ValueError as exc:
            self._show_error_dialog("ERD designer error", str(exc))
            return
        except tk.TclError as exc:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    f"failed to capture rendered canvas ({exc})",
                    "render the ERD and retry export",
                ),
            )
            return
        except OSError as exc:
            self._show_error_dialog(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    f"failed to write export file ({exc})",
                    "check write permissions and destination path",
                ),
            )
            return

        self.status_var.set(f"Exported ERD to {saved_path}.")
