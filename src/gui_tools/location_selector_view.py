import json
import tkinter as tk
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
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

class LocationSelectorToolFrame(ttk.Frame):
    """Interactive map page for selecting a center point and radius-based GeoJSON."""
    ERROR_SURFACE_CONTEXT = "Location selector"
    ERROR_DIALOG_TITLE = "Location selector error"
    WARNING_DIALOG_TITLE = "Location selector warning"

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

    def __init__(
        self,
        parent: tk.Widget,
        app: object,
        cfg: AppConfig,
        *,
        show_header: bool = True,
        title_text: str = "Location Selector",
    ) -> None:
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
        self.error_surface = ErrorSurface(
            context=self.ERROR_SURFACE_CONTEXT,
            dialog_title=self.ERROR_DIALOG_TITLE,
            warning_title=self.WARNING_DIALOG_TITLE,
            show_dialog=show_error_dialog,
            show_warning=show_warning_dialog,
            set_status=self.status_var.set,
        )

        if show_header:
            header = ttk.Frame(self)
            header.pack(fill="x", pady=(0, 8))
            ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
            ttk.Label(header, text=title_text, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))

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

    def _show_error_dialog(self, location: str, message: object) -> str:
        return self.error_surface.emit_exception_actionable(
            message,
            location=(str(location).strip() or "Location selector"),
            hint="review the inputs and retry",
            mode="mixed",
        )

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
            self._show_error_dialog("Location selector error", str(exc))
            return
        self._set_selected_center(lat, lon, source="manual fields")

    def _build_geojson(self) -> None:
        try:
            center_lat, center_lon = self._selected_center_or_error()
            radius_km = parse_radius_km(self.radius_km_var.get())
            steps = parse_geojson_steps(self.geojson_steps_var.get())
            geojson = build_circle_geojson(center_lat, center_lon, radius_km, steps=steps)
        except ValueError as exc:
            self._show_error_dialog("Location selector error", str(exc))
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
            self._show_error_dialog("Location selector error", str(exc))
            return

        self._latest_points = list(points)
        self._set_text(self.sample_points_text, points_to_csv_text(self._latest_points).rstrip("\n"))
        self.status_var.set(
            f"Generated {len(points)} deterministic points for radius={radius_km:.3f} km with seed={seed}."
        )

    def _save_points_csv(self) -> None:
        if not self._latest_points:
            self._show_error_dialog(
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
            self._show_error_dialog("Location selector error", str(exc))
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


