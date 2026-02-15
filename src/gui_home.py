import json
from pathlib import Path
import tkinter as tk
import threading
import time
from tkinter import filedialog, messagebox, ttk

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
from src.gui_execution_orchestrator import ExecutionOrchestratorScreen
from src.gui_kit.scroll import ScrollFrame
from src.gui_schema_project import SchemaProjectDesignerScreen
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen
from src.gui_v2_redesign import ERDDesignerV2Screen
from src.gui_v2_redesign import GenerationBehaviorsGuideV2Screen
from src.gui_v2_redesign import HomeV2Screen
from src.gui_v2_redesign import LocationSelectorV2Screen
from src.gui_v2_redesign import RunCenterV2Screen
from src.gui_v2_redesign import SchemaStudioV2Screen
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
from src.performance_scaling import (
    BenchmarkResult,
    ChunkPlanEntry,
    FK_CACHE_MODES,
    OUTPUT_MODES,
    PerformanceRunCancelled,
    RuntimeEvent,
    StrategyRunResult,
    WorkloadEstimate,
    build_chunk_plan,
    build_performance_profile,
    estimate_workload,
    run_generation_with_strategy,
    run_performance_benchmark,
    summarize_chunk_plan,
    summarize_estimates,
    validate_performance_profile,
)
from src.schema_project_io import load_project_from_json

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
        self.schema_name_var = tk.StringVar(value="new_schema_project")
        self.schema_seed_var = tk.StringVar(value=str(cfg.seed))
        self.table_name_var = tk.StringVar(value="")
        self.table_row_count_var = tk.StringVar(value="100")
        self.column_table_var = tk.StringVar(value="")
        self.column_name_var = tk.StringVar(value="")
        self.column_dtype_var = tk.StringVar(value=ERD_AUTHORING_DTYPES[0])
        self.column_primary_key_var = tk.BooleanVar(value=False)
        self.column_nullable_var = tk.BooleanVar(value=True)
        self.relationship_child_table_var = tk.StringVar(value="")
        self.relationship_child_column_var = tk.StringVar(value="")
        self.relationship_parent_table_var = tk.StringVar(value="")
        self.relationship_parent_column_var = tk.StringVar(value="")
        self.relationship_min_children_var = tk.StringVar(value="1")
        self.relationship_max_children_var = tk.StringVar(value="3")
        self.edit_table_current_var = tk.StringVar(value="")
        self.edit_table_name_var = tk.StringVar(value="")
        self.edit_table_row_count_var = tk.StringVar(value="100")
        self.edit_column_table_var = tk.StringVar(value="")
        self.edit_column_current_var = tk.StringVar(value="")
        self.edit_column_name_var = tk.StringVar(value="")
        self.edit_column_dtype_var = tk.StringVar(value=ERD_AUTHORING_DTYPES[0])
        self.edit_column_primary_key_var = tk.BooleanVar(value=False)
        self.edit_column_nullable_var = tk.BooleanVar(value=True)
        self._authoring_collapsed = False

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="ERD Designer", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=940,
            text=(
                "Load a schema project JSON or create a new schema directly on this page. "
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
        ttk.Button(controls, text="Export schema JSON...", command=self._export_schema_json).grid(
            row=0,
            column=5,
            sticky="ew",
            padx=(8, 0),
        )

        options = ttk.Frame(controls)
        options.grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))
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
        self.authoring_toggle_btn = ttk.Button(
            options,
            text="Collapse schema authoring",
            command=self._toggle_authoring_panel,
        )
        self.authoring_toggle_btn.pack(side="left", padx=(16, 0))

        self.authoring_box = ttk.LabelFrame(self, text="Schema authoring", padding=8)
        self.authoring_box.pack(fill="x", pady=(0, 8))

        schema_row = ttk.Frame(self.authoring_box)
        schema_row.pack(fill="x", pady=(0, 6))
        ttk.Label(schema_row, text="Schema name").pack(side="left")
        ttk.Entry(schema_row, textvariable=self.schema_name_var, width=24).pack(side="left", padx=(8, 12))
        ttk.Label(schema_row, text="Seed").pack(side="left")
        ttk.Entry(schema_row, textvariable=self.schema_seed_var, width=10).pack(side="left", padx=(8, 12))
        ttk.Button(schema_row, text="Create new schema", command=self._create_new_schema).pack(side="left")

        table_row = ttk.Frame(self.authoring_box)
        table_row.pack(fill="x", pady=(0, 6))
        ttk.Label(table_row, text="Table (blank = new)").pack(side="left")
        self.edit_table_current_combo = ttk.Combobox(
            table_row,
            textvariable=self.edit_table_current_var,
            state="readonly",
            width=20,
            values=(),
        )
        self.edit_table_current_combo.pack(side="left", padx=(8, 8))
        self.edit_table_current_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_edit_table_selected())
        ttk.Label(table_row, text="Name").pack(side="left")
        ttk.Entry(table_row, textvariable=self.edit_table_name_var, width=20).pack(side="left", padx=(8, 8))
        ttk.Label(table_row, text="Row count").pack(side="left")
        ttk.Entry(table_row, textvariable=self.edit_table_row_count_var, width=8).pack(side="left", padx=(8, 8))
        ttk.Button(table_row, text="Save table", command=self._save_table_shared).pack(side="left", padx=(8, 4))
        ttk.Button(table_row, text="New table", command=self._reset_table_editor).pack(side="left")

        column_row = ttk.Frame(self.authoring_box)
        column_row.pack(fill="x", pady=(0, 6))
        ttk.Label(column_row, text="Column table").pack(side="left")
        self.edit_column_table_combo = ttk.Combobox(
            column_row,
            textvariable=self.edit_column_table_var,
            state="readonly",
            width=16,
            values=(),
        )
        self.edit_column_table_combo.pack(side="left", padx=(8, 8))
        self.edit_column_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_edit_column_table_changed(),
        )
        ttk.Label(column_row, text="Column (blank = new)").pack(side="left")
        self.edit_column_current_combo = ttk.Combobox(
            column_row,
            textvariable=self.edit_column_current_var,
            state="readonly",
            width=18,
            values=(),
        )
        self.edit_column_current_combo.pack(side="left", padx=(8, 8))
        self.edit_column_current_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_edit_column_selected(),
        )
        ttk.Label(column_row, text="Name").pack(side="left")
        ttk.Entry(column_row, textvariable=self.edit_column_name_var, width=16).pack(side="left", padx=(8, 8))
        ttk.Label(column_row, text="DType").pack(side="left")
        self.edit_column_dtype_combo = ttk.Combobox(
            column_row,
            textvariable=self.edit_column_dtype_var,
            state="readonly",
            width=8,
            values=ERD_AUTHORING_DTYPES,
        )
        self.edit_column_dtype_combo.pack(side="left", padx=(8, 8))
        ttk.Checkbutton(
            column_row,
            text="Primary key",
            variable=self.edit_column_primary_key_var,
            command=self._on_edit_column_pk_changed,
        ).pack(side="left")
        self.edit_column_nullable_check = ttk.Checkbutton(
            column_row,
            text="Nullable",
            variable=self.edit_column_nullable_var,
        )
        self.edit_column_nullable_check.pack(side="left", padx=(8, 8))
        ttk.Button(column_row, text="Save column", command=self._save_column_shared).pack(side="left", padx=(8, 4))
        ttk.Button(column_row, text="New column", command=self._reset_column_editor).pack(side="left")

        relationship_row = ttk.Frame(self.authoring_box)
        relationship_row.pack(fill="x")
        ttk.Label(relationship_row, text="Child table").pack(side="left")
        self.relationship_child_table_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_child_table_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_child_table_combo.pack(side="left", padx=(8, 8))
        self.relationship_child_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_relationship_child_table_changed(),
        )
        ttk.Label(relationship_row, text="Child column").pack(side="left")
        self.relationship_child_column_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_child_column_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_child_column_combo.pack(side="left", padx=(8, 8))
        ttk.Label(relationship_row, text="Parent table").pack(side="left")
        self.relationship_parent_table_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_parent_table_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_parent_table_combo.pack(side="left", padx=(8, 8))
        self.relationship_parent_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._on_relationship_parent_table_changed(),
        )
        ttk.Label(relationship_row, text="Parent column").pack(side="left")
        self.relationship_parent_column_combo = ttk.Combobox(
            relationship_row,
            textvariable=self.relationship_parent_column_var,
            state="readonly",
            width=14,
            values=(),
        )
        self.relationship_parent_column_combo.pack(side="left", padx=(8, 8))
        ttk.Label(relationship_row, text="Min").pack(side="left")
        ttk.Entry(relationship_row, textvariable=self.relationship_min_children_var, width=5).pack(side="left", padx=(6, 4))
        ttk.Label(relationship_row, text="Max").pack(side="left")
        ttk.Entry(relationship_row, textvariable=self.relationship_max_children_var, width=5).pack(side="left", padx=(6, 8))
        ttk.Button(relationship_row, text="Add relationship", command=self._add_relationship).pack(side="left")

        self.diagram_box = ttk.LabelFrame(self, text="ERD preview", padding=8)
        self.diagram_box.pack(fill="both", expand=True)
        self.diagram_box.columnconfigure(0, weight=1)
        self.diagram_box.rowconfigure(0, weight=1)

        self.erd_canvas = tk.Canvas(self.diagram_box, background="#f3f6fb", highlightthickness=1, highlightbackground="#a8b7cc")
        self.erd_canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(self.diagram_box, orient="vertical", command=self.erd_canvas.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(self.diagram_box, orient="horizontal", command=self.erd_canvas.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.erd_canvas.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.erd_canvas.bind("<Configure>", lambda _event: self._draw_erd())
        self.erd_canvas.bind("<ButtonPress-1>", self._on_erd_drag_start)
        self.erd_canvas.bind("<B1-Motion>", self._on_erd_drag_motion)
        self.erd_canvas.bind("<ButtonRelease-1>", self._on_erd_drag_end)

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))
        self._on_column_pk_changed()
        self._on_edit_column_pk_changed()
        self._sync_authoring_controls_from_project()

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

    def _toggle_authoring_panel(self) -> None:
        self._authoring_collapsed = not self._authoring_collapsed
        if self._authoring_collapsed:
            self.authoring_box.pack_forget()
            self.authoring_toggle_btn.configure(text="Expand schema authoring")
            return
        self.authoring_box.pack(fill="x", pady=(0, 8), before=self.diagram_box)
        self.authoring_toggle_btn.configure(text="Collapse schema authoring")

    def _set_combo_values(
        self,
        combo: ttk.Combobox,
        *,
        values: list[str],
        variable: tk.StringVar,
    ) -> None:
        combo.configure(values=tuple(values))
        current = variable.get().strip()
        if current in values:
            variable.set(current)
            return
        if values:
            variable.set(values[0])
            return
        variable.set("")

    def _table_names(self) -> list[str]:
        if self.project is None:
            return []
        return [table.table_name for table in self.project.tables]

    def _table_for_name(self, table_name: str) -> object | None:
        if self.project is None:
            return None
        for table in self.project.tables:
            if table.table_name == table_name:
                return table
        return None

    def _columns_for_table(self, table_name: str, *, primary_key_only: bool = False) -> list[str]:
        if self.project is None:
            return []
        for table in self.project.tables:
            if table.table_name != table_name:
                continue
            if primary_key_only:
                return [column.name for column in table.columns if column.primary_key]
            return [column.name for column in table.columns]
        return []

    def _sync_authoring_controls_from_project(self) -> None:
        table_names = self._table_names()
        self._set_combo_values(
            self.relationship_child_table_combo,
            values=table_names,
            variable=self.relationship_child_table_var,
        )
        self._set_combo_values(
            self.relationship_parent_table_combo,
            values=table_names,
            variable=self.relationship_parent_table_var,
        )
        self._set_combo_values(
            self.edit_table_current_combo,
            values=["", *table_names],
            variable=self.edit_table_current_var,
        )
        self._set_combo_values(
            self.edit_column_table_combo,
            values=table_names,
            variable=self.edit_column_table_var,
        )
        self.column_table_var.set(self.edit_column_table_var.get().strip())
        self._on_column_table_changed()
        self._on_relationship_child_table_changed()
        self._on_relationship_parent_table_changed()
        self._on_edit_table_selected()
        self._on_edit_column_table_changed()

    def _on_column_pk_changed(self) -> None:
        if not hasattr(self, "column_nullable_check"):
            return
        if self.column_primary_key_var.get():
            self.column_nullable_var.set(False)
            self.column_nullable_check.state(["disabled"])
            return
        self.column_nullable_check.state(["!disabled"])

    def _on_column_table_changed(self) -> None:
        # Selection is intentionally retained; no dependent widgets currently require sync.
        _ = self.column_table_var.get().strip()

    def _on_edit_table_selected(self) -> None:
        table_name = self.edit_table_current_var.get().strip()
        table = self._table_for_name(table_name)
        if table is None:
            if table_name == "":
                self.edit_table_name_var.set("")
            self.edit_table_row_count_var.set("100")
            return
        self.edit_table_name_var.set(table.table_name)
        self.edit_table_row_count_var.set(str(table.row_count))

    def _on_edit_column_table_changed(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        column_names = self._columns_for_table(table_name)
        self._set_combo_values(
            self.edit_column_current_combo,
            values=["", *column_names],
            variable=self.edit_column_current_var,
        )
        self._on_edit_column_selected()

    def _on_edit_column_selected(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        column_name = self.edit_column_current_var.get().strip()
        table = self._table_for_name(table_name)
        if table is None or not column_name:
            self.edit_column_name_var.set("")
            self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
            self.edit_column_primary_key_var.set(False)
            self.edit_column_nullable_var.set(True)
            self._on_edit_column_pk_changed()
            return
        selected_column = None
        for column in table.columns:
            if column.name == column_name:
                selected_column = column
                break
        if selected_column is None:
            self.edit_column_name_var.set("")
            self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
            self.edit_column_primary_key_var.set(False)
            self.edit_column_nullable_var.set(True)
            self._on_edit_column_pk_changed()
            return
        self.edit_column_name_var.set(selected_column.name)
        dtype = selected_column.dtype
        if dtype == "float":
            dtype = "decimal"
        if dtype not in ERD_AUTHORING_DTYPES:
            dtype = ERD_AUTHORING_DTYPES[0]
        self.edit_column_dtype_var.set(dtype)
        self.edit_column_primary_key_var.set(bool(selected_column.primary_key))
        self.edit_column_nullable_var.set(bool(selected_column.nullable))
        self._on_edit_column_pk_changed()

    def _on_edit_column_pk_changed(self) -> None:
        if not hasattr(self, "edit_column_nullable_check"):
            return
        if self.edit_column_primary_key_var.get():
            self.edit_column_nullable_var.set(False)
            self.edit_column_nullable_check.state(["disabled"])
            return
        self.edit_column_nullable_check.state(["!disabled"])

    def _reset_table_editor(self) -> None:
        self.edit_table_current_var.set("")
        self.edit_table_name_var.set("")
        self.edit_table_row_count_var.set("100")

    def _reset_column_editor(self) -> None:
        self.edit_column_current_var.set("")
        self.edit_column_name_var.set("")
        self.edit_column_dtype_var.set(ERD_AUTHORING_DTYPES[0])
        self.edit_column_primary_key_var.set(False)
        self.edit_column_nullable_var.set(True)
        self._on_edit_column_pk_changed()

    def _save_table_shared(self) -> None:
        current_table_name = self.edit_table_current_var.get().strip()
        new_table_name = self.edit_table_name_var.get().strip()
        try:
            if current_table_name == "":
                self.project = add_table_to_erd_project(
                    self.project,
                    table_name_value=new_table_name,
                    row_count_value=self.edit_table_row_count_var.get(),
                )
                if self.project is None:
                    return
                self.table_name_var.set(new_table_name)
                self.table_row_count_var.set(self.edit_table_row_count_var.get())
                self.edit_table_current_var.set(new_table_name)
                status_text = f"Added table '{new_table_name}'."
            else:
                self.project = update_table_in_erd_project(
                    self.project,
                    current_table_name_value=current_table_name,
                    new_table_name_value=new_table_name,
                    row_count_value=self.edit_table_row_count_var.get(),
                )
                if current_table_name != new_table_name and current_table_name in self._node_positions:
                    self._node_positions[new_table_name] = self._node_positions.pop(current_table_name)
                self.edit_table_current_var.set(new_table_name)
                status_text = f"Updated table '{current_table_name}' -> '{new_table_name}'."
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(status_text)

    def _save_column_shared(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        current_column_name = self.edit_column_current_var.get().strip()
        new_column_name = self.edit_column_name_var.get().strip()
        self.column_table_var.set(table_name)
        self.column_name_var.set(new_column_name)
        self.column_dtype_var.set(self.edit_column_dtype_var.get())
        self.column_primary_key_var.set(bool(self.edit_column_primary_key_var.get()))
        self.column_nullable_var.set(bool(self.edit_column_nullable_var.get()))
        try:
            if current_column_name == "":
                self.project = add_column_to_erd_project(
                    self.project,
                    table_name_value=table_name,
                    column_name_value=new_column_name,
                    dtype_value=self.edit_column_dtype_var.get(),
                    primary_key=bool(self.edit_column_primary_key_var.get()),
                    nullable=bool(self.edit_column_nullable_var.get()),
                )
                self.edit_column_current_var.set(new_column_name)
                status_text = f"Added column '{table_name}.{new_column_name}'."
            else:
                self.project = update_column_in_erd_project(
                    self.project,
                    table_name_value=table_name,
                    current_column_name_value=current_column_name,
                    new_column_name_value=new_column_name,
                    dtype_value=self.edit_column_dtype_var.get(),
                    primary_key=bool(self.edit_column_primary_key_var.get()),
                    nullable=bool(self.edit_column_nullable_var.get()),
                )
                self.edit_column_current_var.set(new_column_name)
                status_text = (
                    f"Updated column '{table_name}.{current_column_name}' -> '{table_name}.{new_column_name}'."
                )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(status_text)

    def _on_relationship_child_table_changed(self) -> None:
        child_columns = self._columns_for_table(self.relationship_child_table_var.get().strip())
        self._set_combo_values(
            self.relationship_child_column_combo,
            values=child_columns,
            variable=self.relationship_child_column_var,
        )

    def _on_relationship_parent_table_changed(self) -> None:
        parent_columns = self._columns_for_table(
            self.relationship_parent_table_var.get().strip(),
            primary_key_only=True,
        )
        self._set_combo_values(
            self.relationship_parent_column_combo,
            values=parent_columns,
            variable=self.relationship_parent_column_var,
        )

    def _create_new_schema(self) -> None:
        try:
            self.project = new_erd_schema_project(
                name_value=self.schema_name_var.get(),
                seed_value=self.schema_seed_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        self.schema_path_var.set("")
        self._node_positions = {}
        self._node_bounds = {}
        self._node_draw_order = []
        self._drag_table_name = None
        self._drag_offset = None
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(
            f"Created new schema '{self.project.name}' with seed={self.project.seed}. Add tables, columns, and relationships."
        )

    def _add_table(self) -> None:
        try:
            self.project = add_table_to_erd_project(
                self.project,
                table_name_value=self.table_name_var.get(),
                row_count_value=self.table_row_count_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        table_name = self.table_name_var.get().strip()
        self.table_name_var.set("")
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Added table '{table_name}'.")

    def _edit_table(self) -> None:
        current_table_name = self.edit_table_current_var.get().strip()
        new_table_name = self.edit_table_name_var.get().strip()
        try:
            self.project = update_table_in_erd_project(
                self.project,
                current_table_name_value=current_table_name,
                new_table_name_value=new_table_name,
                row_count_value=self.edit_table_row_count_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        if current_table_name != new_table_name and current_table_name in self._node_positions:
            self._node_positions[new_table_name] = self._node_positions.pop(current_table_name)
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Updated table '{current_table_name}' -> '{new_table_name}'.")

    def _add_column(self) -> None:
        try:
            self.project = add_column_to_erd_project(
                self.project,
                table_name_value=self.column_table_var.get(),
                column_name_value=self.column_name_var.get(),
                dtype_value=self.column_dtype_var.get(),
                primary_key=bool(self.column_primary_key_var.get()),
                nullable=bool(self.column_nullable_var.get()),
            )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        column_name = self.column_name_var.get().strip()
        table_name = self.column_table_var.get().strip()
        self.column_name_var.set("")
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Added column '{table_name}.{column_name}'.")

    def _edit_column(self) -> None:
        table_name = self.edit_column_table_var.get().strip()
        current_column_name = self.edit_column_current_var.get().strip()
        new_column_name = self.edit_column_name_var.get().strip()
        try:
            self.project = update_column_in_erd_project(
                self.project,
                table_name_value=table_name,
                current_column_name_value=current_column_name,
                new_column_name_value=new_column_name,
                dtype_value=self.edit_column_dtype_var.get(),
                primary_key=bool(self.edit_column_primary_key_var.get()),
                nullable=bool(self.edit_column_nullable_var.get()),
            )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        self._sync_authoring_controls_from_project()
        self._draw_erd()
        self.status_var.set(f"Updated column '{table_name}.{current_column_name}' -> '{table_name}.{new_column_name}'.")

    def _add_relationship(self) -> None:
        try:
            self.project = add_relationship_to_erd_project(
                self.project,
                child_table_value=self.relationship_child_table_var.get(),
                child_column_value=self.relationship_child_column_var.get(),
                parent_table_value=self.relationship_parent_table_var.get(),
                parent_column_value=self.relationship_parent_column_var.get(),
                min_children_value=self.relationship_min_children_var.get(),
                max_children_value=self.relationship_max_children_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
            return
        child_table = self.relationship_child_table_var.get().strip()
        child_column = self.relationship_child_column_var.get().strip()
        parent_table = self.relationship_parent_table_var.get().strip()
        parent_column = self.relationship_parent_column_var.get().strip()
        self._draw_erd()
        self.status_var.set(
            f"Added relationship '{child_table}.{child_column} -> {parent_table}.{parent_column}'."
        )

    def _load_and_render(self) -> None:
        try:
            self.project = load_project_schema_for_erd(self.schema_path_var.get())
        except ValueError as exc:
            messagebox.showerror("ERD designer error", str(exc))
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
            messagebox.showerror(
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
            messagebox.showerror("ERD designer error", str(exc))
            return

        self.schema_path_var.set(str(saved_path))
        self.status_var.set(f"Exported schema JSON to {saved_path}.")

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


class PerformanceWorkbenchScreen(ttk.Frame):
    """Phase-1 performance profiling and workload diagnostics screen."""

    def __init__(self, parent: tk.Widget, app: "App", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._loaded_schema_path = ""

        self.schema_path_var = tk.StringVar(value="")
        self.target_tables_var = tk.StringVar(value="")
        self.row_overrides_var = tk.StringVar(value="")
        self.preview_row_target_var = tk.StringVar(value="500")
        self.output_mode_var = tk.StringVar(value=OUTPUT_MODES[0])
        self.chunk_size_rows_var = tk.StringVar(value="10000")
        self.preview_page_size_var = tk.StringVar(value="500")
        self.sqlite_batch_size_var = tk.StringVar(value="5000")
        self.csv_buffer_rows_var = tk.StringVar(value="5000")
        self.fk_cache_mode_var = tk.StringVar(value=FK_CACHE_MODES[0])
        self.strict_chunking_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Load a schema and estimate workload strategy.")
        self.live_phase_var = tk.StringVar(value="Idle")
        self.live_rows_var = tk.StringVar(value="Rows processed: 0")
        self.live_eta_var = tk.StringVar(value="ETA: --")
        self._is_running = False
        self._cancel_requested = False
        self._run_started_at = 0.0

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Performance Workbench", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))
        ttk.Button(header, text="Load profile...", command=self._load_profile).pack(side="right")
        ttk.Button(header, text="Save profile...", command=self._save_profile).pack(side="right", padx=(0, 8))

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=940,
            text=(
                "Configure performance profile values, validate FK-safe row overrides, and estimate workload "
                "memory/time before full generation."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        schema_panel = ttk.LabelFrame(self, text="Schema input", padding=8)
        schema_panel.pack(fill="x", pady=(0, 8))
        schema_panel.columnconfigure(1, weight=1)
        ttk.Label(schema_panel, text="Schema project JSON").grid(row=0, column=0, sticky="w")
        ttk.Entry(schema_panel, textvariable=self.schema_path_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(schema_panel, text="Browse...", command=self._browse_schema_path).grid(row=0, column=2, sticky="ew")
        ttk.Button(schema_panel, text="Load schema", command=self._load_schema).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        profile_panel = ttk.LabelFrame(self, text="Workload profile", padding=8)
        profile_panel.pack(fill="x", pady=(0, 8))
        profile_panel.columnconfigure(1, weight=1)

        ttk.Label(profile_panel, text="Target tables (comma-separated)").grid(row=0, column=0, sticky="w")
        ttk.Entry(profile_panel, textvariable=self.target_tables_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 0),
        )

        ttk.Label(profile_panel, text="Row overrides JSON").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.row_overrides_var).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(8, 0),
            pady=(6, 0),
        )

        ttk.Label(profile_panel, text="Preview row target").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.preview_row_target_var).grid(
            row=2,
            column=1,
            sticky="w",
            padx=(8, 0),
            pady=(6, 0),
        )

        ttk.Label(profile_panel, text="Output mode").grid(row=3, column=0, sticky="w", pady=(6, 0))
        output_combo = ttk.Combobox(
            profile_panel,
            textvariable=self.output_mode_var,
            state="readonly",
            values=OUTPUT_MODES,
            width=20,
        )
        output_combo.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        strategy_panel = ttk.LabelFrame(self, text="Execution strategy", padding=8)
        strategy_panel.pack(fill="x", pady=(0, 8))
        for idx in (1, 3):
            strategy_panel.columnconfigure(idx, weight=1)

        ttk.Label(strategy_panel, text="Chunk size rows").grid(row=0, column=0, sticky="w")
        ttk.Entry(strategy_panel, textvariable=self.chunk_size_rows_var).grid(row=0, column=1, sticky="ew", padx=(8, 20))

        ttk.Label(strategy_panel, text="Preview page size").grid(row=0, column=2, sticky="w")
        ttk.Entry(strategy_panel, textvariable=self.preview_page_size_var).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(strategy_panel, text="SQLite batch size").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(strategy_panel, textvariable=self.sqlite_batch_size_var).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(8, 20),
            pady=(6, 0),
        )

        ttk.Label(strategy_panel, text="CSV buffer rows").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(strategy_panel, textvariable=self.csv_buffer_rows_var).grid(
            row=1,
            column=3,
            sticky="ew",
            padx=(8, 0),
            pady=(6, 0),
        )

        ttk.Label(strategy_panel, text="FK cache mode").grid(row=2, column=0, sticky="w", pady=(6, 0))
        fk_cache_combo = ttk.Combobox(
            strategy_panel,
            textvariable=self.fk_cache_mode_var,
            state="readonly",
            values=FK_CACHE_MODES,
            width=20,
        )
        fk_cache_combo.grid(row=2, column=1, sticky="w", padx=(8, 20), pady=(6, 0))

        ttk.Checkbutton(
            strategy_panel,
            text="Strict deterministic chunking",
            variable=self.strict_chunking_var,
        ).grid(row=2, column=2, sticky="w", pady=(6, 0))

        ttk.Button(
            strategy_panel,
            text="Estimate workload",
            command=self._estimate_workload,
        ).grid(row=2, column=3, sticky="e", padx=(8, 0), pady=(6, 0))

        ttk.Button(
            strategy_panel,
            text="Build chunk plan",
            command=self._build_chunk_plan,
        ).grid(row=3, column=3, sticky="e", padx=(8, 0), pady=(6, 0))

        run_controls = ttk.LabelFrame(self, text="Run controls", padding=8)
        run_controls.pack(fill="x", pady=(0, 8))
        run_controls.columnconfigure(0, weight=1)
        run_controls.columnconfigure(1, weight=1)
        run_controls.columnconfigure(2, weight=1)

        self.run_benchmark_btn = ttk.Button(
            run_controls,
            text="Run benchmark",
            command=self._start_run_benchmark,
        )
        self.run_benchmark_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.run_generate_btn = ttk.Button(
            run_controls,
            text="Generate with strategy",
            command=self._start_generate_with_strategy,
        )
        self.run_generate_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.cancel_run_btn = ttk.Button(
            run_controls,
            text="Cancel run",
            command=self._cancel_run,
            state=tk.DISABLED,
        )
        self.cancel_run_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        live_box = ttk.LabelFrame(self, text="Live status", padding=8)
        live_box.pack(fill="x", pady=(0, 8))
        live_box.columnconfigure(0, weight=1)
        self.live_progress = ttk.Progressbar(live_box, mode="determinate", maximum=100.0, value=0.0)
        self.live_progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(live_box, textvariable=self.live_phase_var).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(live_box, textvariable=self.live_rows_var).grid(row=2, column=0, sticky="w")
        ttk.Label(live_box, textvariable=self.live_eta_var).grid(row=3, column=0, sticky="w")

        results = ttk.Notebook(self)
        results.pack(fill="both", expand=True)

        diagnostics_box = ttk.Frame(results, padding=8)
        plan_box = ttk.Frame(results, padding=8)
        results.add(diagnostics_box, text="Diagnostics")
        results.add(plan_box, text="Chunk plan")

        diagnostics_box.columnconfigure(0, weight=1)
        diagnostics_box.rowconfigure(0, weight=1)
        plan_box.columnconfigure(0, weight=1)
        plan_box.rowconfigure(0, weight=1)

        columns = (
            "table",
            "rows",
            "memory_mb",
            "write_mb",
            "seconds",
            "risk",
            "recommendation",
        )
        self.diagnostics_tree = ttk.Treeview(
            diagnostics_box,
            columns=columns,
            show="headings",
            height=10,
        )
        self.diagnostics_tree.grid(row=0, column=0, sticky="nsew")

        headings = {
            "table": "Table",
            "rows": "Estimated rows",
            "memory_mb": "Est. memory (MB)",
            "write_mb": "Est. write (MB)",
            "seconds": "Est. time (s)",
            "risk": "Risk",
            "recommendation": "Recommendation",
        }
        widths = {
            "table": 160,
            "rows": 120,
            "memory_mb": 130,
            "write_mb": 120,
            "seconds": 110,
            "risk": 90,
            "recommendation": 420,
        }
        for column in columns:
            self.diagnostics_tree.heading(column, text=headings[column], anchor="w")
            self.diagnostics_tree.column(column, width=widths[column], anchor="w", stretch=(column == "recommendation"))

        tree_scroll_y = ttk.Scrollbar(diagnostics_box, orient="vertical", command=self.diagnostics_tree.yview)
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x = ttk.Scrollbar(diagnostics_box, orient="horizontal", command=self.diagnostics_tree.xview)
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        self.diagnostics_tree.configure(
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
        )

        plan_columns = (
            "table",
            "stage",
            "chunk_index",
            "start_row",
            "end_row",
            "rows_in_chunk",
        )
        self.chunk_plan_tree = ttk.Treeview(
            plan_box,
            columns=plan_columns,
            show="headings",
            height=10,
        )
        self.chunk_plan_tree.grid(row=0, column=0, sticky="nsew")

        plan_headings = {
            "table": "Table",
            "stage": "Stage",
            "chunk_index": "Chunk",
            "start_row": "Start row",
            "end_row": "End row",
            "rows_in_chunk": "Rows",
        }
        plan_widths = {
            "table": 220,
            "stage": 100,
            "chunk_index": 100,
            "start_row": 140,
            "end_row": 140,
            "rows_in_chunk": 120,
        }
        for column in plan_columns:
            self.chunk_plan_tree.heading(column, text=plan_headings[column], anchor="w")
            self.chunk_plan_tree.column(column, width=plan_widths[column], anchor="w")

        plan_scroll_y = ttk.Scrollbar(plan_box, orient="vertical", command=self.chunk_plan_tree.yview)
        plan_scroll_y.grid(row=0, column=1, sticky="ns")
        plan_scroll_x = ttk.Scrollbar(plan_box, orient="horizontal", command=self.chunk_plan_tree.xview)
        plan_scroll_x.grid(row=1, column=0, sticky="ew")
        self.chunk_plan_tree.configure(
            yscrollcommand=plan_scroll_y.set,
            xscrollcommand=plan_scroll_x.set,
        )

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def _perf_error(self, field: str, issue: str, hint: str) -> str:
        return f"Performance Workbench / {field}: {issue}. Fix: {hint}."

    def _browse_schema_path(self) -> None:
        path = filedialog.askopenfilename(
            title="Select schema project JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.schema_path_var.set(path)

    def _load_schema(self) -> bool:
        schema_path = self.schema_path_var.get().strip()
        if schema_path == "":
            messagebox.showerror(
                "Performance workbench error",
                self._perf_error(
                    "Schema path",
                    "path is required",
                    "browse to an existing schema project JSON file",
                ),
            )
            return False
        try:
            loaded = load_project_from_json(schema_path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return False
        self.project = loaded
        self._loaded_schema_path = schema_path
        self._clear_diagnostics()
        self._clear_chunk_plan()
        self.status_var.set(
            f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables. Configure profile and estimate workload."
        )
        return True

    def _build_profile(self):
        return build_performance_profile(
            target_tables_value=self.target_tables_var.get(),
            row_overrides_json_value=self.row_overrides_var.get(),
            preview_row_target_value=self.preview_row_target_var.get(),
            output_mode_value=self.output_mode_var.get(),
            chunk_size_rows_value=self.chunk_size_rows_var.get(),
            preview_page_size_value=self.preview_page_size_var.get(),
            sqlite_batch_size_value=self.sqlite_batch_size_var.get(),
            csv_buffer_rows_value=self.csv_buffer_rows_var.get(),
            fk_cache_mode_value=self.fk_cache_mode_var.get(),
            strict_deterministic_chunking_value=self.strict_chunking_var.get(),
        )

    def _ensure_project(self) -> bool:
        path_now = self.schema_path_var.get().strip()
        if self.project is None:
            return self._load_schema()
        if path_now == "":
            return True
        if path_now != self._loaded_schema_path:
            return self._load_schema()
        return True

    def _estimate_workload(self) -> None:
        if self._is_running:
            return
        if not self._ensure_project():
            return
        assert self.project is not None
        try:
            profile = self._build_profile()
            validate_performance_profile(self.project, profile)
            estimates = estimate_workload(self.project, profile)
        except ValueError as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return
        self._populate_estimates(estimates)
        summary = summarize_estimates(estimates)
        self.status_var.set(
            "Estimate complete: "
            f"rows={summary.total_rows}, memory={summary.total_memory_mb:.3f} MB, "
            f"write={summary.total_write_mb:.3f} MB, time={summary.total_seconds:.3f} s, "
            f"highest risk={summary.highest_risk}."
        )

    def _build_chunk_plan(self) -> None:
        if self._is_running:
            return
        if not self._ensure_project():
            return
        assert self.project is not None
        try:
            profile = self._build_profile()
            plan_entries = build_chunk_plan(self.project, profile)
        except ValueError as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return
        self._populate_chunk_plan(plan_entries)
        plan_summary = summarize_chunk_plan(plan_entries)
        self.status_var.set(
            "Chunk plan ready: "
            f"tables={plan_summary.table_count}, chunks={plan_summary.total_chunks}, "
            f"rows={plan_summary.total_rows}, max stage={plan_summary.max_stage}."
        )

    def _populate_estimates(self, estimates: list[WorkloadEstimate]) -> None:
        self._clear_diagnostics()
        for estimate in estimates:
            self.diagnostics_tree.insert(
                "",
                "end",
                values=(
                    estimate.table_name,
                    str(estimate.estimated_rows),
                    f"{estimate.estimated_memory_mb:.3f}",
                    f"{estimate.estimated_write_mb:.3f}",
                    f"{estimate.estimated_seconds:.3f}",
                    estimate.risk_level,
                    estimate.recommendation,
                ),
            )

    def _populate_chunk_plan(self, entries: list[ChunkPlanEntry]) -> None:
        self._clear_chunk_plan()
        for entry in entries:
            self.chunk_plan_tree.insert(
                "",
                "end",
                values=(
                    entry.table_name,
                    str(entry.stage),
                    str(entry.chunk_index),
                    str(entry.start_row),
                    str(entry.end_row),
                    str(entry.rows_in_chunk),
                ),
            )

    def _clear_diagnostics(self) -> None:
        for item in self.diagnostics_tree.get_children():
            self.diagnostics_tree.delete(item)

    def _clear_chunk_plan(self) -> None:
        for item in self.chunk_plan_tree.get_children():
            self.chunk_plan_tree.delete(item)

    def _set_running(self, running: bool, phase: str) -> None:
        self._is_running = running
        self.live_phase_var.set(phase)
        if running:
            self._run_started_at = time.monotonic()
            self._cancel_requested = False
            self.cancel_run_btn.configure(state=tk.NORMAL)
            self.run_benchmark_btn.configure(state=tk.DISABLED)
            self.run_generate_btn.configure(state=tk.DISABLED)
        else:
            self.cancel_run_btn.configure(state=tk.DISABLED)
            self.run_benchmark_btn.configure(state=tk.NORMAL)
            self.run_generate_btn.configure(state=tk.NORMAL)

    def _cancel_run(self) -> None:
        if not self._is_running:
            return
        self._cancel_requested = True
        self.live_phase_var.set("Cancelling...")
        self.status_var.set("Cancellation requested. Waiting for current step to finish...")

    def _is_cancel_requested(self) -> bool:
        return self._cancel_requested

    def _on_runtime_event(self, event: RuntimeEvent) -> None:
        if event.kind == "started":
            self.live_progress.configure(value=0.0)
            self.live_phase_var.set(event.message or "Run started.")
            self.live_rows_var.set(f"Rows processed: 0/{event.total_rows}")
            self.live_eta_var.set("ETA: calculating...")
            return

        if event.kind in {"progress", "table_done"}:
            total_rows = max(1, event.total_rows)
            processed = max(0, event.rows_processed)
            percent = min(100.0, (float(processed) / float(total_rows)) * 100.0)
            self.live_progress.configure(value=percent)
            self.live_phase_var.set(event.message or "Running...")
            self.live_rows_var.set(f"Rows processed: {processed}/{event.total_rows}")

            elapsed = max(0.001, time.monotonic() - self._run_started_at)
            rate = processed / elapsed
            if rate <= 0.0:
                self.live_eta_var.set("ETA: --")
            else:
                remaining = max(0, event.total_rows - processed)
                eta_seconds = int(round(float(remaining) / rate))
                self.live_eta_var.set(f"ETA: {eta_seconds}s @ {rate:.1f} rows/s")
            return

        if event.kind == "run_done":
            self.live_progress.configure(value=100.0)
            self.live_phase_var.set(event.message or "Run complete.")
            self.live_rows_var.set(f"Rows processed: {event.rows_processed}/{event.total_rows}")
            elapsed = max(0.001, time.monotonic() - self._run_started_at)
            rate = float(event.rows_processed) / elapsed if event.rows_processed > 0 else 0.0
            self.live_eta_var.set(f"Completed in {elapsed:.2f}s @ {rate:.1f} rows/s")
            return

        if event.kind == "cancelled":
            self.live_phase_var.set(event.message or "Run cancelled.")
            self.live_eta_var.set("ETA: cancelled")
            return

    def _run_worker(self, target, *, phase_label: str) -> None:
        if self._is_running:
            return
        self._set_running(True, phase_label)

        def work() -> None:
            try:
                target()
            except PerformanceRunCancelled as exc:
                self.after(0, lambda: self._on_run_cancelled(str(exc)))
            except ValueError as exc:
                self.after(0, lambda: self._on_run_failed(str(exc)))
            except Exception as exc:
                self.after(0, lambda: self._on_run_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _on_run_failed(self, message: str) -> None:
        self._set_running(False, "Failed")
        self.status_var.set(message)
        messagebox.showerror("Performance workbench error", message)

    def _on_run_cancelled(self, message: str) -> None:
        self._set_running(False, "Cancelled")
        self._on_runtime_event(RuntimeEvent(kind="cancelled", message="Run cancelled by user."))
        self.status_var.set(message)

    def _on_benchmark_done(self, result: BenchmarkResult) -> None:
        self._populate_estimates(result.estimates)
        self._populate_chunk_plan(result.chunk_plan)
        self._set_running(False, "Benchmark complete")
        self.status_var.set(
            "Benchmark complete: "
            f"tables={len(result.selected_tables)}, chunks={result.chunk_summary.total_chunks}, "
            f"rows={result.chunk_summary.total_rows}, "
            f"risk={result.estimate_summary.highest_risk}."
        )

    def _on_generate_done(self, result: StrategyRunResult) -> None:
        self._set_running(False, "Generation complete")
        csv_count = len(result.csv_paths)
        sqlite_rows = sum(result.sqlite_counts.values())
        self.status_var.set(
            "Generation complete: "
            f"tables={len(result.selected_tables)}, rows={result.total_rows}, "
            f"csv_files={csv_count}, sqlite_rows={sqlite_rows}."
        )

    def _start_run_benchmark(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        try:
            profile = self._build_profile()
        except ValueError as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return

        def target() -> None:
            result = run_performance_benchmark(
                self.project,
                profile,
                on_event=lambda e: self.after(0, lambda evt=e: self._on_runtime_event(evt)),
                cancel_requested=self._is_cancel_requested,
            )
            self.after(0, lambda: self._on_benchmark_done(result))

        self._run_worker(target, phase_label="Running benchmark...")

    def _start_generate_with_strategy(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        try:
            profile = self._build_profile()
        except ValueError as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return

        output_mode = profile.output_mode
        output_csv_folder: str | None = None
        output_sqlite_path: str | None = None
        if output_mode in {"csv", "all"}:
            output_csv_folder = filedialog.askdirectory(title="Choose output folder for strategy CSV export")
            if output_csv_folder in {None, ""}:
                self.status_var.set("Generate with strategy cancelled (no CSV output folder).")
                return
        if output_mode in {"sqlite", "all"}:
            output_sqlite_path = filedialog.asksaveasfilename(
                title="Choose SQLite output path for strategy run",
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
                initialfile="performance_strategy.db",
            )
            if output_sqlite_path in {None, ""}:
                self.status_var.set("Generate with strategy cancelled (no SQLite output path).")
                return

        def target() -> None:
            result = run_generation_with_strategy(
                self.project,
                profile,
                output_csv_folder=output_csv_folder,
                output_sqlite_path=output_sqlite_path,
                on_event=lambda e: self.after(0, lambda evt=e: self._on_runtime_event(evt)),
                cancel_requested=self._is_cancel_requested,
            )
            self.after(0, lambda: self._on_generate_done(result))

        self._run_worker(target, phase_label="Generating with strategy...")

    def _save_profile(self) -> None:
        try:
            profile = self._build_profile()
        except ValueError as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return
        output_path = filedialog.asksaveasfilename(
            title="Save performance profile JSON",
            defaultextension=".json",
            initialfile="performance_profile.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.status_var.set("Save profile cancelled.")
            return
        payload = {
            "target_tables": list(profile.target_tables),
            "row_overrides": profile.row_overrides,
            "preview_row_target": profile.preview_row_target,
            "output_mode": profile.output_mode,
            "chunk_size_rows": profile.chunk_size_rows,
            "preview_page_size": profile.preview_page_size,
            "sqlite_batch_size": profile.sqlite_batch_size,
            "csv_buffer_rows": profile.csv_buffer_rows,
            "fk_cache_mode": profile.fk_cache_mode,
            "strict_deterministic_chunking": profile.strict_deterministic_chunking,
        }
        try:
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(
                "Performance workbench error",
                self._perf_error(
                    "Save profile",
                    f"could not write profile file ({exc})",
                    "choose a writable output path",
                ),
            )
            return
        self.status_var.set(f"Saved performance profile to {output_path}.")

    def _load_profile(self) -> None:
        profile_path = filedialog.askopenfilename(
            title="Load performance profile JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if profile_path == "":
            self.status_var.set("Load profile cancelled.")
            return
        try:
            payload = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror(
                "Performance workbench error",
                self._perf_error(
                    "Load profile",
                    f"failed to read profile JSON ({exc})",
                    "choose a valid JSON profile file",
                ),
            )
            return
        if not isinstance(payload, dict):
            messagebox.showerror(
                "Performance workbench error",
                self._perf_error(
                    "Load profile",
                    "profile JSON must be an object",
                    "store profile fields in a JSON object",
                ),
            )
            return
        try:
            self.target_tables_var.set(", ".join(payload.get("target_tables", [])))
            row_overrides = payload.get("row_overrides", {})
            if row_overrides in ({}, None):
                self.row_overrides_var.set("")
            else:
                self.row_overrides_var.set(json.dumps(row_overrides, separators=(",", ":")))
            self.preview_row_target_var.set(str(payload.get("preview_row_target", 500)))
            self.output_mode_var.set(str(payload.get("output_mode", OUTPUT_MODES[0])))
            self.chunk_size_rows_var.set(str(payload.get("chunk_size_rows", 10000)))
            self.preview_page_size_var.set(str(payload.get("preview_page_size", 500)))
            self.sqlite_batch_size_var.set(str(payload.get("sqlite_batch_size", 5000)))
            self.csv_buffer_rows_var.set(str(payload.get("csv_buffer_rows", 5000)))
            self.fk_cache_mode_var.set(str(payload.get("fk_cache_mode", FK_CACHE_MODES[0])))
            self.strict_chunking_var.set(bool(payload.get("strict_deterministic_chunking", True)))
            # Re-validate profile immediately so bad files fail early with actionable guidance.
            self._build_profile()
        except ValueError as exc:
            messagebox.showerror("Performance workbench error", str(exc))
            return
        self.status_var.set(f"Loaded performance profile from {profile_path}.")


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

        ttk.Button(
            card,
            text="Performance Workbench -> configure chunking profile and estimate workload",
            command=lambda: self.app.show_screen("performance_workbench"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Execution Orchestrator -> multiprocessing partition planning and worker run monitor",
            command=lambda: self.app.show_screen("execution_orchestrator"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text=(
                "Visual Redesign Preview (v2) -> home_v2 / schema_studio_v2 / run_center_v2 "
                "/ erd_designer_v2 / location_selector_v2 / generation_behaviors_guide_v2"
            ),
            command=lambda: self.app.show_screen("home_v2"),
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
        self.screens["performance_workbench"] = PerformanceWorkbenchScreen(self.screen_container, self, cfg)
        self.screens["execution_orchestrator"] = ExecutionOrchestratorScreen(self.screen_container, self, cfg)
        self.screens["home_v2"] = HomeV2Screen(self.screen_container, self)
        self.screens["schema_studio_v2"] = SchemaStudioV2Screen(self.screen_container, self, cfg)
        self.screens["run_center_v2"] = RunCenterV2Screen(self.screen_container, self, cfg)
        self.screens["erd_designer_v2"] = ERDDesignerV2Screen(self.screen_container, self, cfg)
        self.screens["location_selector_v2"] = LocationSelectorV2Screen(self.screen_container, self, cfg)
        self.screens["generation_behaviors_guide_v2"] = GenerationBehaviorsGuideV2Screen(
            self.screen_container,
            self,
            cfg,
        )

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
