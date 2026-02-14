import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.config import AppConfig
from src.erd_designer import (
    apply_node_position_overrides,
    build_erd_layout,
    build_erd_svg,
    compute_diagram_size,
    edge_label,
    export_erd_file,
    load_project_schema_for_erd,
    node_anchor_y,
    table_for_edge,
)
from src.gui_kit.scroll import ScrollFrame
from src.gui_schema_project import SchemaProjectDesignerScreen
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen
from src.location_selector import (
    build_circle_geojson,
    build_circle_ring,
    normalize_longitude,
    parse_geojson_steps,
    parse_latitude,
    parse_longitude,
    parse_radius_km,
    parse_sample_count,
    parse_seed,
    points_to_csv_text,
    sample_points_within_radius,
    write_points_csv,
)

GuideEntry = tuple[str, str, str]

GENERATION_BEHAVIOR_GUIDE: tuple[GuideEntry, ...] = (
    (
        "Default dtype generation",
        "When Generator is blank, values are generated from the column dtype and constraints using project.seed.",
        "Set DType and optional constraints in the Column editor (for bytes use params JSON min_length/max_length). Use Pattern preset for common regex cases and keep Generator empty.",
    ),
    (
        "Guided generator authoring",
        "The Generator dropdown is filtered by selected DType and can auto-fill starter params.",
        "Pick DType first, then choose Generator from the filtered list, and click 'Fill params template for selected generator' to avoid writing full params JSON from scratch.",
    ),
    (
        "sample_csv generator",
        "Samples deterministic values from a CSV column and can optionally match rows by another generated column.",
        "Set Generator='sample_csv' and params JSON like {\"path\": \"tests/fixtures/city_country_pool.csv\", \"column_index\": 0}. For dependent sampling (for example city by country), add params.match_column and params.match_column_index, and include match_column in Depends on column.",
    ),
    (
        "if_then conditional generator",
        "Returns then_value or else_value based on another column in the same row.",
        "Set Generator='if_then', include params.if_column/operator/value/then_value/else_value, and set Depends on column to include if_column.",
    ),
    (
        "time_offset time-aware generator",
        "Constrains date/datetime output to be before or after another time column in the same row.",
        "Set Generator='time_offset', include params.base_column and optional direction ('after'/'before') plus min/max offsets (date: min_days/max_days, datetime: min_seconds/max_seconds), and include base_column in Depends on column.",
    ),
    (
        "hierarchical_category generator",
        "Generates child categories from a parent category column using a hierarchy mapping.",
        "Set Generator='hierarchical_category', include params.parent_column and params.hierarchy JSON, and include parent_column in Depends on column.",
    ),
    (
        "date generator",
        "Generates ISO date values in a configured range.",
        "Set Generator='date' and params JSON like {\"start\": \"2020-01-01\", \"end\": \"2026-12-31\"}.",
    ),
    (
        "timestamp_utc generator",
        "Generates UTC timestamps in ISO 8601 format with Z suffix.",
        "Set Generator='timestamp_utc' and params JSON like {\"start\": \"2020-01-01T00:00:00Z\", \"end\": \"2026-12-31T23:59:59Z\"}.",
    ),
    (
        "latitude/longitude generators",
        "Generates decimal-like geographic coordinates with bounds and decimal precision control.",
        "Set Generator='latitude' or 'longitude' and optional params {\"min\": ..., \"max\": ..., \"decimals\": ...}.",
    ),
    (
        "money/percent generators",
        "Generates bounded numeric values suited to financial or percentage fields.",
        "Use DType='decimal', then set Generator='money' or 'percent' with optional min/max/decimals params.",
    ),
    (
        "Distribution generators",
        "Supports realistic normal, uniform, and lognormal numeric distributions with deterministic seed behavior.",
        "Set Generator to 'normal', 'uniform_int', 'uniform_float', or 'lognormal' in the Column editor, then provide Params JSON for bounds/shape (for example mean/stdev or median/sigma).",
    ),
    (
        "Weighted categorical generator",
        "Generates category values using explicit weighted probabilities.",
        "Set Generator='choice_weighted' and Params JSON like {\"choices\": [\"A\", \"B\"], \"weights\": [0.8, 0.2]}.",
    ),
    (
        "ordered_choice sequence generator",
        "Chooses one named order path and progresses through that sequence over rows using weighted movement steps.",
        "Set Generator='ordered_choice' with params.orders, optional params.order_weights, params.move_weights, and optional params.start_index (for example {\"orders\": {\"A\": [\"1\", \"2\", \"3\"], \"B\": [\"4\", \"5\", \"6\"]}, \"order_weights\": {\"A\": 0.5, \"B\": 0.5}, \"move_weights\": [0.1, 0.8, 0.1], \"start_index\": 0}).",
    ),
    (
        "Correlated generator via depends_on (advanced JSON)",
        "Builds one column from another column in the same row.",
        "Use Generator='salary_from_age' (or another correlated generator), set required params, and include source columns in depends_on.",
    ),
    (
        "Business key + SCD table behaviors",
        "Table-level SCD1/SCD2 settings control overwrite vs versioned history behavior tied to business keys.",
        "Use Selected table fields for Business key columns, static/changing columns, SCD mode, tracked columns, and SCD2 active-period columns.",
    ),
)


class GenerationBehaviorsGuideScreen(ttk.Frame):
    """Read-only reference page for generation behaviors supported by the app."""

    def __init__(self, parent: tk.Widget, app: "App") -> None:
        super().__init__(parent, padding=16)
        self.app = app

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Data Generation Behaviors Guide", font=("Segoe UI", 16, "bold")).pack(
            side="left",
            padx=(10, 0),
        )

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=900,
            text=(
                "This page explains each supported data generation behavior and how to configure it "
                "in the current schema designer workflow."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        self.scroll = ScrollFrame(self, padding=0)
        self.scroll.pack(fill="both", expand=True)

        for title, what_it_does, how_to_use in GENERATION_BEHAVIOR_GUIDE:
            self._add_entry(title, what_it_does, how_to_use)

    def _add_entry(self, title: str, what_it_does: str, how_to_use: str) -> None:
        card = ttk.LabelFrame(self.scroll.content, text=title, padding=10)
        card.pack(fill="x", pady=(0, 8))
        ttk.Label(
            card,
            text=f"What it does: {what_it_does}",
            justify="left",
            wraplength=880,
        ).pack(anchor="w")
        ttk.Label(
            card,
            text=f"How to use: {how_to_use}",
            justify="left",
            wraplength=880,
        ).pack(anchor="w", pady=(6, 0))


class ERDDesignerScreen(ttk.Frame):
    """Schema-to-diagram view for table/column/FK relationship inspection."""

    def __init__(self, parent: tk.Widget, app: "App", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._last_diagram_width = 1200
        self._last_diagram_height = 800
        self._node_positions: dict[str, tuple[int, int]] = {}
        self._node_bounds: dict[str, tuple[int, int, int, int]] = {}
        self._node_draw_order: list[str] = []
        self._drag_table_name: str | None = None
        self._drag_offset: tuple[float, float] | None = None

        self.schema_path_var = tk.StringVar(value="")
        self.show_relationships_var = tk.BooleanVar(value=True)
        self.show_columns_var = tk.BooleanVar(value=True)
        self.show_dtypes_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Load a project schema JSON file to render ERD.")

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="ERD Designer", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=940,
            text=(
                "Load a schema project JSON and render a relational ER diagram. "
                "Toggle relationships, column names, and datatypes for different views. "
                "Drag table cards to rearrange layout."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        controls = ttk.LabelFrame(self, text="Input + display options", padding=8)
        controls.pack(fill="x", pady=(0, 8))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Schema project JSON").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.schema_path_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(controls, text="Browse...", command=self._browse_schema_path).grid(row=0, column=2, sticky="ew")
        ttk.Button(controls, text="Render ERD", command=self._load_and_render).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(8, 0),
        )
        ttk.Button(controls, text="Export ERD...", command=self._export_erd).grid(
            row=0,
            column=4,
            sticky="ew",
            padx=(8, 0),
        )

        options = ttk.Frame(controls)
        options.grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            options,
            text="Show relationships",
            variable=self.show_relationships_var,
            command=self._on_options_changed,
        ).pack(side="left")
        ttk.Checkbutton(
            options,
            text="Show column names",
            variable=self.show_columns_var,
            command=self._on_options_changed,
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            options,
            text="Show datatypes",
            variable=self.show_dtypes_var,
            command=self._on_options_changed,
        ).pack(side="left", padx=(12, 0))

        diagram_box = ttk.LabelFrame(self, text="ERD preview", padding=8)
        diagram_box.pack(fill="both", expand=True)
        diagram_box.columnconfigure(0, weight=1)
        diagram_box.rowconfigure(0, weight=1)

        self.erd_canvas = tk.Canvas(diagram_box, background="#f3f6fb", highlightthickness=1, highlightbackground="#a8b7cc")
        self.erd_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(diagram_box, orient="vertical", command=self.erd_canvas.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(diagram_box, orient="horizontal", command=self.erd_canvas.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.erd_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.erd_canvas.bind("<Configure>", lambda _event: self._draw_erd())
        self.erd_canvas.bind("<ButtonPress-1>", self._on_erd_drag_start)
        self.erd_canvas.bind("<B1-Motion>", self._on_erd_drag_motion)
        self.erd_canvas.bind("<ButtonRelease-1>", self._on_erd_drag_end)

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def _erd_error(self, field: str, issue: str, hint: str) -> str:
        return f"ERD Designer / {field}: {issue}. Fix: {hint}."

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
            messagebox.showerror("ERD designer error", str(exc))
            return
        self._node_positions = {}
        self._node_bounds = {}
        self._node_draw_order = []
        self._drag_table_name = None
        self._drag_offset = None
        self._draw_erd()

    def _export_erd(self) -> None:
        if self.project is None:
            messagebox.showerror(
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
            messagebox.showerror("ERD designer error", str(exc))
            return
        except tk.TclError as exc:
            messagebox.showerror(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    f"failed to capture rendered canvas ({exc})",
                    "render the ERD and retry export",
                ),
            )
            return
        except OSError as exc:
            messagebox.showerror(
                "ERD designer error",
                self._erd_error(
                    "Export",
                    f"failed to write export file ({exc})",
                    "check write permissions and destination path",
                ),
            )
            return

        self.status_var.set(f"Exported ERD to {saved_path}.")

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

    def _table_name_at_canvas_point(self, x: float, y: float) -> str | None:
        for table_name in reversed(self._node_draw_order):
            bounds = self._node_bounds.get(table_name)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            if x1 <= x <= x2 and y1 <= y <= y2:
                return table_name
        return None

    def _on_erd_drag_start(self, event: tk.Event) -> None:
        if self.project is None:
            return
        canvas_x = float(self.erd_canvas.canvasx(event.x))
        canvas_y = float(self.erd_canvas.canvasy(event.y))
        table_name = self._table_name_at_canvas_point(canvas_x, canvas_y)
        if table_name is None:
            self._drag_table_name = None
            self._drag_offset = None
            return
        bounds = self._node_bounds.get(table_name)
        if bounds is None:
            return
        self._drag_table_name = table_name
        self._drag_offset = (canvas_x - bounds[0], canvas_y - bounds[1])

    def _on_erd_drag_motion(self, event: tk.Event) -> None:
        if self._drag_table_name is None or self._drag_offset is None:
            return
        canvas_x = float(self.erd_canvas.canvasx(event.x))
        canvas_y = float(self.erd_canvas.canvasy(event.y))
        next_x = max(16, int(canvas_x - self._drag_offset[0]))
        next_y = max(16, int(canvas_y - self._drag_offset[1]))
        self._node_positions[self._drag_table_name] = (next_x, next_y)
        self._draw_erd()

    def _on_erd_drag_end(self, _event: tk.Event) -> None:
        self._drag_table_name = None
        self._drag_offset = None


class LocationSelectorScreen(ttk.Frame):
    """Interactive map page for selecting a center point and radius-based GeoJSON."""

    LAND_POLYGONS: tuple[tuple[tuple[float, float], ...], ...] = (
        (
            (-56.0, -82.0),
            (-10.0, -80.0),
            (8.0, -72.0),
            (23.0, -86.0),
            (52.0, -127.0),
            (70.0, -162.0),
            (72.0, -135.0),
            (60.0, -80.0),
            (16.0, -55.0),
            (-34.0, -46.0),
            (-55.0, -58.0),
        ),
        (
            (36.0, -10.0),
            (43.0, 15.0),
            (58.0, 40.0),
            (66.0, 90.0),
            (72.0, 150.0),
            (56.0, 170.0),
            (43.0, 140.0),
            (29.0, 120.0),
            (15.0, 95.0),
            (8.0, 62.0),
            (20.0, 35.0),
            (35.0, -5.0),
        ),
        (
            (-35.0, -17.0),
            (-5.0, -12.0),
            (18.0, 5.0),
            (35.0, 32.0),
            (32.0, 52.0),
            (10.0, 48.0),
            (-34.0, 33.0),
        ),
        (
            (-45.0, 112.0),
            (-12.0, 112.0),
            (-10.0, 154.0),
            (-42.0, 154.0),
        ),
        (
            (60.0, -52.0),
            (72.0, -44.0),
            (83.0, -26.0),
            (76.0, -12.0),
            (64.0, -24.0),
            (60.0, -44.0),
        ),
        (
            (-90.0, -180.0),
            (-90.0, 180.0),
            (-60.0, 180.0),
            (-60.0, -180.0),
        ),
    )

    def __init__(self, parent: tk.Widget, app: "App", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg

        self.map_zoom = 1.0
        self.map_pan_x = 0.0
        self.map_pan_y = 0.0
        self._pan_anchor: tuple[int, int] | None = None
        self.selected_lat: float | None = None
        self.selected_lon: float | None = None
        self._latest_points: list[tuple[float, float]] = []

        self.center_lat_var = tk.StringVar(value="")
        self.center_lon_var = tk.StringVar(value="")
        self.radius_km_var = tk.StringVar(value="100")
        self.geojson_steps_var = tk.StringVar(value="72")
        self.sample_count_var = tk.StringVar(value="100")
        self.sample_seed_var = tk.StringVar(value=str(cfg.seed))
        self.status_var = tk.StringVar(value="Click map to select a center point.")

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Location Selector", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=920,
            text=(
                "Select a center point, set a radius in km, and generate a GeoJSON circle plus deterministic sample points "
                "for latitude/longitude authoring workflows."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        map_box = ttk.LabelFrame(body, text="Map", padding=8)
        map_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        map_box.columnconfigure(0, weight=1)
        map_box.rowconfigure(0, weight=1)

        self.map_canvas = tk.Canvas(
            map_box,
            bg="#d9ecff",
            highlightthickness=1,
            highlightbackground="#7aa6d6",
            width=560,
            height=280,
            cursor="crosshair",
        )
        self.map_canvas.grid(row=0, column=0, sticky="nsew")
        self.map_canvas.bind("<Configure>", lambda _event: self._redraw_map())
        self.map_canvas.bind("<Button-1>", self._on_map_click)
        self.map_canvas.bind("<MouseWheel>", self._on_map_wheel)
        self.map_canvas.bind("<Button-4>", lambda event: self._zoom_around_point(event.x, event.y, 1.2))
        self.map_canvas.bind("<Button-5>", lambda event: self._zoom_around_point(event.x, event.y, 1.0 / 1.2))
        self.map_canvas.bind("<ButtonPress-3>", self._on_pan_start)
        self.map_canvas.bind("<B3-Motion>", self._on_pan_move)
        self.map_canvas.bind("<ButtonRelease-3>", self._on_pan_end)
        self.map_canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.map_canvas.bind("<B2-Motion>", self._on_pan_move)
        self.map_canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        controls = ttk.LabelFrame(body, text="Selection controls", padding=8)
        controls.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Latitude").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.center_lat_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(controls, text="Longitude").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.center_lon_var).grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(controls, text="Radius (km)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.radius_km_var).grid(row=2, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(controls, text="GeoJSON steps").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.geojson_steps_var).grid(row=3, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(controls, text="Sample count").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.sample_count_var).grid(row=4, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(controls, text="Sample seed").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.sample_seed_var).grid(row=5, column=1, sticky="ew", pady=(6, 0))

        control_buttons = ttk.Frame(controls)
        control_buttons.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        control_buttons.columnconfigure(0, weight=1)
        control_buttons.columnconfigure(1, weight=1)
        ttk.Button(control_buttons, text="Set center from fields", command=self._set_center_from_fields).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(control_buttons, text="Zoom in", command=lambda: self._zoom_around_center(1.2)).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(0, 4),
            pady=(0, 6),
        )
        ttk.Button(control_buttons, text="Zoom out", command=lambda: self._zoom_around_center(1.0 / 1.2)).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(4, 0),
            pady=(0, 6),
        )
        ttk.Button(control_buttons, text="Reset view", command=self._reset_map_view).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(control_buttons, text="Build GeoJSON", command=self._build_geojson).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(control_buttons, text="Generate sample points", command=self._generate_points).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 6),
        )
        ttk.Button(control_buttons, text="Save points CSV...", command=self._save_points_csv).grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="ew",
        )

        geojson_box = ttk.LabelFrame(body, text="GeoJSON output", padding=8)
        geojson_box.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        geojson_box.columnconfigure(0, weight=1)
        geojson_box.rowconfigure(0, weight=1)
        self.geojson_text = tk.Text(geojson_box, height=10, wrap="none")
        self.geojson_text.grid(row=0, column=0, sticky="nsew")
        geo_scroll_y = ttk.Scrollbar(geojson_box, orient="vertical", command=self.geojson_text.yview)
        geo_scroll_y.grid(row=0, column=1, sticky="ns")
        geo_scroll_x = ttk.Scrollbar(geojson_box, orient="horizontal", command=self.geojson_text.xview)
        geo_scroll_x.grid(row=1, column=0, sticky="ew")
        self.geojson_text.configure(yscrollcommand=geo_scroll_y.set, xscrollcommand=geo_scroll_x.set)
        self._set_text(self.geojson_text, "{}")

        sample_box = ttk.LabelFrame(body, text="Sample latitude/longitude points", padding=8)
        sample_box.grid(row=1, column=1, sticky="nsew")
        sample_box.columnconfigure(0, weight=1)
        sample_box.rowconfigure(0, weight=1)
        self.sample_points_text = tk.Text(sample_box, height=10, wrap="none")
        self.sample_points_text.grid(row=0, column=0, sticky="nsew")
        sample_scroll_y = ttk.Scrollbar(sample_box, orient="vertical", command=self.sample_points_text.yview)
        sample_scroll_y.grid(row=0, column=1, sticky="ns")
        sample_scroll_x = ttk.Scrollbar(sample_box, orient="horizontal", command=self.sample_points_text.xview)
        sample_scroll_x.grid(row=1, column=0, sticky="ew")
        self.sample_points_text.configure(
            yscrollcommand=sample_scroll_y.set,
            xscrollcommand=sample_scroll_x.set,
        )
        self._set_text(
            self.sample_points_text,
            "Click the map, set radius, and generate deterministic samples.",
        )

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))
        self._redraw_map()

    def _location_error(self, field: str, issue: str, hint: str) -> str:
        return f"Location Selector / {field}: {issue}. Fix: {hint}."

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _canvas_size(self) -> tuple[float, float]:
        width = max(2.0, float(self.map_canvas.winfo_width()))
        height = max(2.0, float(self.map_canvas.winfo_height()))
        return width, height

    def _latlon_to_canvas(self, lat: float, lon: float) -> tuple[float, float]:
        width, height = self._canvas_size()
        base_x = ((normalize_longitude(lon) + 180.0) / 360.0) * width
        base_y = ((90.0 - lat) / 180.0) * height
        x = (base_x - (width / 2.0)) * self.map_zoom + (width / 2.0) + self.map_pan_x
        y = (base_y - (height / 2.0)) * self.map_zoom + (height / 2.0) + self.map_pan_y
        return x, y

    def _canvas_to_latlon(self, x: float, y: float) -> tuple[float, float]:
        width, height = self._canvas_size()
        base_x = ((x - self.map_pan_x - (width / 2.0)) / self.map_zoom) + (width / 2.0)
        base_y = ((y - self.map_pan_y - (height / 2.0)) / self.map_zoom) + (height / 2.0)
        lon = (base_x / width) * 360.0 - 180.0
        lat = 90.0 - ((base_y / height) * 180.0)
        lat = max(-90.0, min(90.0, lat))
        lon = normalize_longitude(lon)
        return lat, lon

    def _set_selected_center(self, lat: float, lon: float, source: str) -> None:
        self.selected_lat = lat
        self.selected_lon = lon
        self.center_lat_var.set(f"{lat:.6f}")
        self.center_lon_var.set(f"{lon:.6f}")
        self.status_var.set(f"Center set from {source}: lat={lat:.6f}, lon={lon:.6f}.")
        self._redraw_map()

    def _selected_center_or_error(self) -> tuple[float, float]:
        if self.selected_lat is None or self.selected_lon is None:
            raise ValueError(
                self._location_error(
                    "Center point",
                    "no center point is selected",
                    "click the map or enter latitude/longitude and apply center",
                )
            )
        return self.selected_lat, self.selected_lon

    def _on_map_click(self, event: tk.Event) -> None:
        lat, lon = self._canvas_to_latlon(float(event.x), float(event.y))
        self._set_selected_center(lat, lon, source="map click")

    def _on_map_wheel(self, event: tk.Event) -> None:
        if event.delta == 0:
            return
        factor = 1.2 if event.delta > 0 else 1.0 / 1.2
        self._zoom_around_point(float(event.x), float(event.y), factor)

    def _zoom_around_center(self, factor: float) -> None:
        width, height = self._canvas_size()
        self._zoom_around_point(width / 2.0, height / 2.0, factor)

    def _zoom_around_point(self, x: float, y: float, factor: float) -> None:
        next_zoom = min(16.0, max(1.0, self.map_zoom * factor))
        if abs(next_zoom - self.map_zoom) < 1e-9:
            return
        lat, lon = self._canvas_to_latlon(x, y)
        self.map_zoom = next_zoom
        new_x, new_y = self._latlon_to_canvas(lat, lon)
        self.map_pan_x += x - new_x
        self.map_pan_y += y - new_y
        self._redraw_map()

    def _on_pan_start(self, event: tk.Event) -> None:
        self._pan_anchor = (event.x, event.y)

    def _on_pan_move(self, event: tk.Event) -> None:
        if self._pan_anchor is None:
            return
        dx = event.x - self._pan_anchor[0]
        dy = event.y - self._pan_anchor[1]
        self._pan_anchor = (event.x, event.y)
        self.map_pan_x += dx
        self.map_pan_y += dy
        self._redraw_map()

    def _on_pan_end(self, _event: tk.Event) -> None:
        self._pan_anchor = None

    def _reset_map_view(self) -> None:
        self.map_zoom = 1.0
        self.map_pan_x = 0.0
        self.map_pan_y = 0.0
        self._redraw_map()

    def _set_center_from_fields(self) -> None:
        try:
            lat = parse_latitude(self.center_lat_var.get())
            lon = parse_longitude(self.center_lon_var.get())
        except ValueError as exc:
            messagebox.showerror("Location selector error", str(exc))
            return
        self._set_selected_center(lat, lon, source="manual fields")

    def _build_geojson(self) -> None:
        try:
            center_lat, center_lon = self._selected_center_or_error()
            radius_km = parse_radius_km(self.radius_km_var.get())
            steps = parse_geojson_steps(self.geojson_steps_var.get())
            geojson = build_circle_geojson(center_lat, center_lon, radius_km, steps=steps)
        except ValueError as exc:
            messagebox.showerror("Location selector error", str(exc))
            return
        self._set_text(self.geojson_text, json.dumps(geojson, indent=2))
        self.status_var.set(
            f"GeoJSON generated for lat={center_lat:.6f}, lon={center_lon:.6f}, radius={radius_km:.3f} km."
        )
        self._redraw_map()

    def _generate_points(self) -> None:
        try:
            center_lat, center_lon = self._selected_center_or_error()
            radius_km = parse_radius_km(self.radius_km_var.get())
            count = parse_sample_count(self.sample_count_var.get())
            seed = parse_seed(self.sample_seed_var.get())
            points = sample_points_within_radius(
                center_lat,
                center_lon,
                radius_km,
                count=count,
                seed=seed,
            )
        except ValueError as exc:
            messagebox.showerror("Location selector error", str(exc))
            return

        self._latest_points = list(points)
        self._set_text(self.sample_points_text, points_to_csv_text(self._latest_points).rstrip("\n"))
        self.status_var.set(
            f"Generated {len(points)} deterministic points for radius={radius_km:.3f} km with seed={seed}."
        )

    def _save_points_csv(self) -> None:
        if not self._latest_points:
            messagebox.showerror(
                "Location selector error",
                self._location_error(
                    "Save points CSV",
                    "no sampled points are available",
                    "click 'Generate sample points' before saving",
                ),
            )
            return

        save_path = filedialog.asksaveasfilename(
            title="Save location points CSV",
            defaultextension=".csv",
            initialfile="location_selector_points.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if save_path == "":
            self.status_var.set("Save points CSV cancelled.")
            return

        try:
            output_path = write_points_csv(save_path, self._latest_points)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Location selector error", str(exc))
            return

        self.status_var.set(f"Saved {len(self._latest_points)} sample points to {output_path}.")

    def _draw_graticule(self) -> None:
        for lon in range(-180, 181, 30):
            x1, y1 = self._latlon_to_canvas(-85.0, float(lon))
            x2, y2 = self._latlon_to_canvas(85.0, float(lon))
            self.map_canvas.create_line(x1, y1, x2, y2, fill="#b8d4ef", width=1)
        for lat in range(-60, 91, 30):
            x1, y1 = self._latlon_to_canvas(float(lat), -180.0)
            x2, y2 = self._latlon_to_canvas(float(lat), 180.0)
            self.map_canvas.create_line(x1, y1, x2, y2, fill="#b8d4ef", width=1)
        eq_x1, eq_y1 = self._latlon_to_canvas(0.0, -180.0)
        eq_x2, eq_y2 = self._latlon_to_canvas(0.0, 180.0)
        self.map_canvas.create_line(eq_x1, eq_y1, eq_x2, eq_y2, fill="#91bfe8", width=2)
        pm_x1, pm_y1 = self._latlon_to_canvas(-90.0, 0.0)
        pm_x2, pm_y2 = self._latlon_to_canvas(90.0, 0.0)
        self.map_canvas.create_line(pm_x1, pm_y1, pm_x2, pm_y2, fill="#91bfe8", width=2)

    def _draw_land_polygons(self) -> None:
        for polygon in self.LAND_POLYGONS:
            canvas_points: list[float] = []
            for lat, lon in polygon:
                x, y = self._latlon_to_canvas(lat, lon)
                canvas_points.extend([x, y])
            self.map_canvas.create_polygon(
                canvas_points,
                fill="#d9dcc1",
                outline="#8a8c6f",
                width=1,
            )

    def _draw_selected_geometry(self) -> None:
        if self.selected_lat is None or self.selected_lon is None:
            return
        center_x, center_y = self._latlon_to_canvas(self.selected_lat, self.selected_lon)
        self.map_canvas.create_oval(
            center_x - 4.0,
            center_y - 4.0,
            center_x + 4.0,
            center_y + 4.0,
            fill="#d12f2f",
            outline="#7f1010",
            width=1,
        )
        self.map_canvas.create_line(center_x - 8.0, center_y, center_x + 8.0, center_y, fill="#7f1010", width=1)
        self.map_canvas.create_line(center_x, center_y - 8.0, center_x, center_y + 8.0, fill="#7f1010", width=1)

        try:
            radius_km = parse_radius_km(self.radius_km_var.get())
            ring = build_circle_ring(self.selected_lat, self.selected_lon, radius_km, steps=96)
        except ValueError:
            return
        ring_points: list[float] = []
        for lon, lat in ring:
            x, y = self._latlon_to_canvas(float(lat), float(lon))
            ring_points.extend([x, y])
        self.map_canvas.create_line(ring_points, fill="#d12f2f", width=2, smooth=True)

    def _redraw_map(self) -> None:
        self.map_canvas.delete("all")
        width, height = self._canvas_size()
        self.map_canvas.create_rectangle(0, 0, width, height, fill="#d9ecff", outline="#7aa6d6")
        self._draw_graticule()
        self._draw_land_polygons()
        self._draw_selected_geometry()


class HomeScreen(ttk.Frame):
    """
    Home screen focused on Schema Project MVP workflow.
    """
    def __init__(self, parent: tk.Widget, app: "App") -> None:
        super().__init__(parent, padding=16)
        self.app = app

        title = ttk.Label(self, text="Generic Data Application", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        subtitle = ttk.Label(
            self,
            text="Schema Project MVP: design multi-table schemas and generate relational data.",
        )
        subtitle.pack(anchor="w", pady=(0, 16))

        card = ttk.LabelFrame(self, text="Tool", padding=12)
        card.pack(fill="x")

        ttk.Button(
            card,
            text="Schema Project Designer (Production) -> modular layout, tables/FKs/generation/JSON/SQLite",
            command=lambda: self.app.show_screen("schema_project"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Schema Project Designer (Kit Preview) -> modular layout components",
            command=lambda: self.app.show_screen("schema_project_kit"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Schema Project Designer (Legacy Fallback) -> pre-modular screen",
            command=lambda: self.app.show_screen("schema_project_legacy"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Data Generation Behaviors Guide -> explanation and setup patterns",
            command=lambda: self.app.show_screen("generation_behaviors_guide"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="ERD Designer -> schema JSON to interactive entity relationship diagram",
            command=lambda: self.app.show_screen("erd_designer"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Location Selector -> map point/radius to GeoJSON and latitude/longitude samples",
            command=lambda: self.app.show_screen("location_selector"),
        ).pack(fill="x", pady=6)


class App(ttk.Frame):
    """
    App container that manages screens and switches between them.
    """
    def __init__(self, root: tk.Tk, cfg: AppConfig) -> None:
        super().__init__(root)
        self.root = root
        self.cfg = cfg

        self.root.title("Generic Data Application")
        self.root.geometry("960x540")

        self.pack(fill="both", expand=True)

        self.screen_container = ttk.Frame(self)
        self.screen_container.pack(fill="both", expand=True)

        self.screens: dict[str, ttk.Frame] = {}
        self.screens["home"] = HomeScreen(self.screen_container, self)
        self.screens["schema_project"] = SchemaProjectDesignerKitScreen(self.screen_container, self, cfg)
        self.screens["schema_project_kit"] = SchemaProjectDesignerKitScreen(self.screen_container, self, cfg)
        self.screens["schema_project_legacy"] = SchemaProjectDesignerScreen(self.screen_container, self, cfg)
        self.screens["generation_behaviors_guide"] = GenerationBehaviorsGuideScreen(self.screen_container, self)
        self.screens["erd_designer"] = ERDDesignerScreen(self.screen_container, self, cfg)
        self.screens["location_selector"] = LocationSelectorScreen(self.screen_container, self, cfg)

        for frame in self.screens.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self.screen_container.rowconfigure(0, weight=1)
        self.screen_container.columnconfigure(0, weight=1)

        self.show_screen("home")

    def show_screen(self, name: str) -> None:
        if name not in self.screens:
            available = ", ".join(sorted(self.screens.keys()))
            raise KeyError(
                f"Unknown screen '{name}' in App.show_screen. "
                f"Available screens: {available}. "
                "Fix: call show_screen() with one of the available names."
            )
        self.screens[name].tkraise()

    def go_home(self) -> None:
        self.show_screen("home")
