import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.gui_kit.scroll import ScrollFrame
from src.gui_schema_project import SchemaProjectDesignerScreen
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen

GuideEntry = tuple[str, str, str]

GENERATION_BEHAVIOR_GUIDE: tuple[GuideEntry, ...] = (
    (
        "Default dtype generation",
        "When Generator is blank, values are generated from the column dtype and constraints using project.seed.",
        "Set DType and optional Min/Max, Choices, and Pattern in the Column editor. Keep Generator empty.",
    ),
    (
        "sample_csv generator",
        "Samples deterministic values from a CSV column and reuses the source distribution.",
        "Set Generator='sample_csv' and params JSON like {\"path\": \"tests/fixtures/city_country_pool.csv\", \"column_index\": 0}.",
    ),
    (
        "if_then conditional generator",
        "Returns then_value or else_value based on another column in the same row.",
        "Set Generator='if_then', include params.if_column/operator/value/then_value/else_value, and set Depends on column to include if_column.",
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
        "Distribution generators (advanced JSON)",
        "Supports normal, uniform, and lognormal distributions for specialized modeling.",
        "Load/edit JSON with generator ids 'normal', 'uniform_int', 'uniform_float', or 'lognormal', and provide the documented params for each.",
    ),
    (
        "Weighted categorical generator (advanced JSON)",
        "Generates category values using explicit weighted probabilities.",
        "Load/edit JSON with Generator='choice_weighted' and params like {\"choices\": [\"A\", \"B\"], \"weights\": [0.8, 0.2]}.",
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
