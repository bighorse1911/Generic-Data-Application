from email import header
import json
import logging
import tkinter as tk
import threading
import csv
import os
import tkinter.font as tkfont
from src.generator_project import generate_project_rows
from src.storage_sqlite_project import create_tables, insert_project_rows
from dataclasses import dataclass

from tkinter import ttk, messagebox, filedialog

from src.config import AppConfig
from src.schema_project_model import (
    SchemaProject,
    TableSpec,
    ColumnSpec,
    ForeignKeySpec,
    validate_project,
)
from src.schema_project_io import save_project_to_json, load_project_from_json

logger = logging.getLogger("gui_schema_project")

DTYPES = ["int", "decimal", "text", "bool", "date", "datetime"]
GENERATORS = ["", "sample_csv", "date", "timestamp_utc", "latitude", "longitude", "money", "percent"]
SCD_MODES = ["", "scd1", "scd2"]
EXPORT_OPTION_CSV = "CSV (folder)"
EXPORT_OPTION_SQLITE = "SQLite (database)"
EXPORT_OPTIONS = [EXPORT_OPTION_CSV, EXPORT_OPTION_SQLITE]


def validate_export_option(option: object) -> str:
    value = option.strip() if isinstance(option, str) else ""
    if value in EXPORT_OPTIONS:
        return value
    allowed = ", ".join(EXPORT_OPTIONS)
    raise ValueError(
        "Generate / Preview / Export / SQLite panel: unsupported export option "
        f"'{option}'. Fix: choose one of: {allowed}."
    )



# ---------------- Scrollable logic ----------------
class ScrollableFrame(ttk.Frame):
    """
    A ttk.Frame that can scroll both vertically and horizontally.

    Internals:
    - A Canvas does the scrolling.
    - An 'inner' Frame lives inside the Canvas and holds your actual widgets.
    - Scrollbars are attached to the Canvas.
    """
    def __init__(self, parent: tk.Widget, *, padding: int = 0) -> None:
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        # Layout: canvas takes most space, scrollbars on right and bottom
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # Inner frame: where you will place all your widgets
        self.inner = ttk.Frame(self.canvas, padding=padding)
        self._inner_window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # When inner frame resizes, update scrollable area
        self.inner.bind("<Configure>", self._on_inner_configure)
        # When canvas resizes, keep inner frame width synced if desired
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling (Windows/macOS/Linux variants)
        self._bind_mousewheel(self.canvas)

        #Zoom Logic
        self.zoom = 1.0
        self.min_zoom = 0.7
        self.max_zoom = 1.5
        self.zoom_step = 0.1

        #Base font to enable zooming
        self._fonts = {}
        for name in ("TkDefaultFont", "TkTextFont", "TkFixedFont"):
            f = tkfont.nametofont(name)
            self._fonts[name] = {
                "font": f,
                "size": f.cget("size"),
            }


    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        # If you want the inner frame to expand to canvas width, uncomment:
        # self.canvas.itemconfigure(self._inner_window_id, width=event.width)
        # If you want horizontal scrolling to work, do NOT force width.
        pass

    def _bind_mousewheel(self, widget: tk.Widget) -> None:
        # Windows: <MouseWheel>, Linux: Button-4/5, macOS uses <MouseWheel> too but delta differs.
        widget.bind_all("<MouseWheel>", self._on_mousewheel)     # Windows/macOS
        widget.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
        widget.bind_all("<Button-4>", self._on_linux_wheel_up)   # Linux
        widget.bind_all("<Button-5>", self._on_linux_wheel_down)
        widget.bind_all("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        widget.bind_all("<Control-plus>", lambda e: self.zoom_in())
        widget.bind_all("<Control-minus>", lambda e: self.zoom_out())
        widget.bind_all("<Control-0>", lambda e: self.reset_zoom())


    def _on_mousewheel(self, event) -> None:
        # Vertical scroll
        if event.delta and self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mousewheel(self, event) -> None:
        # Horizontal scroll (hold Shift)
        if event.delta and self.canvas.winfo_exists():
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_linux_wheel_up(self, _event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(-1, "units")

    def _on_linux_wheel_down(self, _event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(1, "units")
    # Zooming methods
    def zoom_in(self) -> None:
        self._apply_zoom(self.zoom + self.zoom_step)

    def zoom_out(self) -> None:
        self._apply_zoom(self.zoom - self.zoom_step)

    def reset_zoom(self) -> None:
        self._apply_zoom(1.0)
    def _apply_zoom(self, new_zoom: float) -> None:
        if not self.canvas.winfo_exists():
            return
        new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        if abs(new_zoom - self.zoom) < 0.001:
            return

        self.zoom = new_zoom

        for meta in self._fonts.values():
            base = meta["size"]
            meta["font"].configure(size=int(base * self.zoom))

        # Update scroll region after resizing
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def scale_treeview_columns(tree: ttk.Treeview, factor: float) -> None:
        for col in tree["columns"]:
            w = tree.column(col, "width")
            tree.column(col, width=int(w * factor))


    def _on_ctrl_mousewheel(self, event) -> None:
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()


# ---------------- Collapse widgets/sections ----------------
class CollapsibleSection(ttk.Frame):
    """
    A collapsible panel with a header row and a content frame.

    Usage:
        section = CollapsibleSection(parent, title="Tables")
        section.pack(fill="both", expand=True)
        # put widgets inside:
        ttk.Label(section.content, text="Hello").pack()
    """
    def __init__(self, parent: tk.Widget, title: str, *, start_collapsed: bool = False) -> None:
        super().__init__(parent)

        self._collapsed = tk.BooleanVar(value=start_collapsed)

        # Header
        header = ttk.Frame(self)
        header.pack(fill="x")

        self._btn = ttk.Button(header, width=3, command=self.toggle)
        self._btn.pack(side="left")

        self._title_lbl = ttk.Label(header, text=title, font=("Segoe UI", 10, "bold"))
        self._title_lbl.pack(side="left", padx=(6, 0))

        # Make header clickable too
        self._title_lbl.bind("<Button-1>", lambda e: self.toggle())
        header.bind("<Button-1>", lambda e: self.toggle())

        # Content
        self.content = ttk.Frame(self)
        if not start_collapsed:
            self.content.pack(fill="both", expand=True, pady=(6, 0))

        self._sync_button()

    def _sync_button(self) -> None:
        # ▾ expanded, ▸ collapsed
        self._btn.configure(text="▸" if self._collapsed.get() else "▾")

    def toggle(self) -> None:
        if self._collapsed.get():
            self.expand()
        else:
            self.collapse()

    def collapse(self) -> None:
        if not self._collapsed.get():
            self._collapsed.set(True)
            self.content.pack_forget()
            self._sync_button()

    def expand(self) -> None:
        if self._collapsed.get():
            self._collapsed.set(False)
            self.content.pack(fill="both", expand=True, pady=(6, 0))
            self._sync_button()

    @property
    def is_collapsed(self) -> bool:
        return bool(self._collapsed.get())

# ---------------- Heatmaps to check validity of schema ----------------


@dataclass(frozen=True)
class ValidationIssue:
    severity: str   # "ok" | "warn" | "error"
    scope: str      # "project" | "table" | "column" | "fk"
    table: str | None
    column: str | None
    message: str


class ValidationHeatmap(ttk.Frame):
    """
    Canvas-based heatmap:

    - rows: tables
    - cols: checks
    - cell color: ok/warn/error
    - click cell: show details
    """
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)

        self.canvas = tk.Canvas(self, height=220, highlightthickness=0)
        self.h = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.v = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h.set, yscrollcommand=self.v.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v.grid(row=0, column=1, sticky="ns")
        self.h.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._tables: list[str] = []
        self._checks: list[str] = []
        self._cell_details: dict[tuple[int, int], list[str]] = {}

        self._cell_w = 120
        self._cell_h = 28
        self._pad = 6

        self.canvas.bind("<Button-1>", self._on_click)

    def set_data(
        self,
        tables: list[str],
        checks: list[str],
        status: dict[tuple[str, str], str],
        details: dict[tuple[str, str], list[str]],
    ) -> None:
        """
        status[(table, check)] = "ok"|"warn"|"error"
        details[(table, check)] = list of messages
        """
        self._tables = tables
        self._checks = checks

        self._cell_details.clear()
        for ti, t in enumerate(tables):
            for ci, c in enumerate(checks):
                msgs = details.get((t, c), [])
                self._cell_details[(ti, ci)] = msgs

        self._draw(status)

    def _color(self, sev: str) -> str:
        # Keep colors subtle so text is readable
        if sev == "error":
            return "#f7b5b5"
        if sev == "warn":
            return "#ffe39a"
        return "#bfe8bf"

    def _draw(self, status: dict[tuple[str, str], str]) -> None:
        self.canvas.delete("all")

        # Header row (checks)
        x0 = self._pad + self._cell_w  # leave space for table names on left
        y0 = self._pad

        for ci, check in enumerate(self._checks):
            x = x0 + ci * self._cell_w
            self.canvas.create_rectangle(x, y0, x + self._cell_w, y0 + self._cell_h, fill="#e9e9e9", outline="#999")
            self.canvas.create_text(x + 6, y0 + self._cell_h / 2, text=check, anchor="w", font=("Segoe UI", 9, "bold"))

        # Table names + cells
        for ti, table in enumerate(self._tables):
            y = y0 + self._cell_h + ti * self._cell_h

            # table name cell
            self.canvas.create_rectangle(self._pad, y, self._pad + self._cell_w, y + self._cell_h, fill="#e9e9e9", outline="#999")
            self.canvas.create_text(self._pad + 6, y + self._cell_h / 2, text=table, anchor="w", font=("Segoe UI", 9, "bold"))

            for ci, check in enumerate(self._checks):
                x = x0 + ci * self._cell_w
                sev = status.get((table, check), "ok")
                self.canvas.create_rectangle(x, y, x + self._cell_w, y + self._cell_h, fill=self._color(sev), outline="#999")

                # Small label
                label = "OK" if sev == "ok" else ("WARN" if sev == "warn" else "ERR")
                self.canvas.create_text(x + self._cell_w / 2, y + self._cell_h / 2, text=label, font=("Segoe UI", 9))

        total_w = x0 + len(self._checks) * self._cell_w + self._pad
        total_h = y0 + (len(self._tables) + 1) * self._cell_h + self._pad
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _hit_test(self, x: int, y: int) -> tuple[int, int] | None:
        # translate x/y into table/check indices (excluding headers)
        x0 = self._pad + self._cell_w
        y0 = self._pad + self._cell_h

        if x < x0 or y < y0:
            return None

        ci = (x - x0) // self._cell_w
        ti = (y - y0) // self._cell_h

        if ti < 0 or ti >= len(self._tables):
            return None
        if ci < 0 or ci >= len(self._checks):
            return None
        return int(ti), int(ci)

    def _on_click(self, event) -> None:
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        hit = self._hit_test(x, y)
        if not hit:
            return
        ti, ci = hit
        msgs = self._cell_details.get((ti, ci), [])
        if not msgs:
            messagebox.showinfo("Validation", "No issues.")
            return
        messagebox.showinfo("Validation details", "\n".join(msgs))


# ---------------- The actual screen ----------------
class SchemaProjectDesignerScreen(ttk.Frame):
    """
    Schema Project Designer (Phase 1 + Phase 2):
    - Manage tables in a project
    - Edit selected table (name + row_count)
    - Edit selected table columns (add/remove/move, set PK)
    - Define FK relationships (parent->child) with cardinality min/max children
    - Save/load full project JSON
    """
    def __init__(self, parent: tk.Widget, app: "object", cfg: AppConfig) -> None:
        super().__init__(parent)
        self.app = app
        self.cfg = cfg

        #Scrollable container logic
        self.scroll = ScrollableFrame(self, padding=16)
        self.scroll.pack(fill="both", expand=True)



        # In-memory project
        self.project = SchemaProject(name="my_project", seed=cfg.seed, tables=[], foreign_keys=[])

        # Selection state
        self.selected_table_index: int | None = None

        # Project-level vars
        self.project_name_var = tk.StringVar(value=self.project.name)
        self.seed_var = tk.StringVar(value=str(self.project.seed))
        self.status_var = tk.StringVar(value="Ready.")

        # Table editor vars
        self.table_name_var = tk.StringVar(value="")
        self.row_count_var = tk.StringVar(value="100")
        self.table_business_key_var = tk.StringVar(value="")
        self.table_scd_mode_var = tk.StringVar(value="")
        self.table_scd_tracked_columns_var = tk.StringVar(value="")
        self.table_scd_active_from_var = tk.StringVar(value="")
        self.table_scd_active_to_var = tk.StringVar(value="")

        # Column form vars
        self.col_name_var = tk.StringVar(value="")
        self.col_dtype_var = tk.StringVar(value="text")
        self.col_nullable_var = tk.BooleanVar(value=True)
        self.col_pk_var = tk.BooleanVar(value=False)
        self.col_unique_var = tk.BooleanVar(value=False)
        self.col_min_var = tk.StringVar(value="")
        self.col_max_var = tk.StringVar(value="")
        self.col_choices_var = tk.StringVar(value="")
        self.col_pattern_var = tk.StringVar(value="")

        #Updated data generation variables
        self.col_generator_var = tk.StringVar(value="")
        self.col_params_var = tk.StringVar(value="")  # JSON text

        self.col_depends_var = tk.StringVar(value="")


        # Relationship editor vars
        self.fk_parent_table_var = tk.StringVar(value="")
        self.fk_child_table_var = tk.StringVar(value="")
        self.fk_child_column_var = tk.StringVar(value="")
        self.fk_min_children_var = tk.StringVar(value="1")
        self.fk_max_children_var = tk.StringVar(value="3")

        #Validation
        self.validation_summary_var = tk.StringVar(value="No validation run yet.")


        # Generation/preview state
        self.is_running = False
        self.generated_rows: dict[str, list[dict[str, object]]] = {}

        # Output / DB vars
        self.db_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "schema_project.db"))
        self.export_option_var = tk.StringVar(value=EXPORT_OPTION_CSV)
        self.preview_table_var = tk.StringVar(value="")

        #Validation state variables
        self.last_validation_errors = 0
        self.last_validation_warnings = 0


        self._build()
        self._refresh_tables_list()
        self._set_table_editor_enabled(False)
        self._refresh_fk_dropdowns()
        self._refresh_fks_tree()

        #Final validation
        self._run_validation()


    # ---------------- UI layout ----------------
    def _build(self) -> None:
        root = self.scroll.inner

        # =========================
        # Header (pack on root)
        # =========================
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 10))

        ttk.Button(header, text="← Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Schema Project Designer", font=("Segoe UI", 16, "bold")).pack(side="left", padx=12)
        ttk.Button(header, text="Zoom +", command=self.scroll.zoom_in).pack(side="top", padx=0)
        ttk.Button(header, text="Zoom −", command=self.scroll.zoom_out).pack(side="top", padx=0)
        ttk.Button(header, text="Reset", command=self.scroll.reset_zoom).pack(side="top", padx=0)


        # =========================
        # Project bar (grid inside proj)
        # =========================
        proj = ttk.LabelFrame(root, text="Project", padding=12)
        proj.pack(fill="x")

        proj.columnconfigure(1, weight=1)

        ttk.Label(proj, text="Project name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(proj, textvariable=self.project_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(proj, text="Seed:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ttk.Entry(proj, textvariable=self.seed_var, width=12).grid(row=0, column=3, sticky="w", padx=6, pady=6)

        btns = ttk.Frame(proj)
        btns.grid(row=1, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Save project JSON", command=self._save_project).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(btns, text="Load project JSON", command=self._load_project).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        # Validation Panels
        validation_section = CollapsibleSection(root, title="Schema validation", start_collapsed=False)
        validation_section.pack(fill="x", pady=(10, 0))

        validation_panel = ttk.LabelFrame(validation_section.content, text="", padding=10)
        validation_panel.pack(fill="x", expand=True)

        top = ttk.Frame(validation_panel)
        top.pack(fill="x")

        ttk.Button(top, text="Run validation", command=self._run_validation).pack(side="left")

        self.validation_summary_var = tk.StringVar(value="No validation run yet.")
        ttk.Label(top, textvariable=self.validation_summary_var).pack(side="left", padx=10)

        self.heatmap = ValidationHeatmap(validation_panel)
        self.heatmap.pack(fill="both", expand=True, pady=(8, 0))


        # =========================
        # Main area: Tables | Table editor | Relationships
        # (pack main on root; grid inside main)
        # =========================
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, pady=(10, 0))

        main.columnconfigure(0, weight=1)  # tables
        main.columnconfigure(1, weight=3)  # table editor
        main.columnconfigure(2, weight=2)  # relationships
        main.rowconfigure(0, weight=1)

        # ---- Left: tables list (pack inside left)
        left_section = CollapsibleSection(main, title="Tables")
        left_section.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left = ttk.LabelFrame(left_section.content, text="", padding=10)  # inner panel
        left.pack(fill="both", expand=True)


        self.tables_list = tk.Listbox(left, height=12)
        self.tables_list.pack(fill="both", expand=True)
        self.tables_list.bind("<<ListboxSelect>>", self._on_table_selected)

        left_btns = ttk.Frame(left)
        left_btns.pack(fill="x", pady=(10, 0))
        ttk.Button(left_btns, text="+ Add table", command=self._add_table).pack(fill="x", pady=4)
        ttk.Button(left_btns, text="Remove selected", command=self._remove_table).pack(fill="x", pady=4)

        # ---- Middle: table editor (pack inside right)
        right_section = CollapsibleSection(main, title="Table editor")
        right_section.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        right = ttk.LabelFrame(right_section.content, text="", padding=10)
        right.pack(fill="both", expand=True)

        # Table properties (grid inside props)
        props = ttk.LabelFrame(right, text="Table properties", padding=10)
        props.pack(fill="x")
        props.columnconfigure(1, weight=1)

        ttk.Label(props, text="Table name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.table_name_entry = ttk.Entry(props, textvariable=self.table_name_var)
        self.table_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(props, text="Row count (root tables (0 for children enables auto-sizing)):").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.row_count_entry = ttk.Entry(props, textvariable=self.row_count_var)
        self.row_count_entry.grid(row=1, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(props, text="Business key columns (comma):").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.table_business_key_entry = ttk.Entry(props, textvariable=self.table_business_key_var)
        self.table_business_key_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(props, text="SCD mode:").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        self.table_scd_mode_combo = ttk.Combobox(
            props,
            values=SCD_MODES,
            textvariable=self.table_scd_mode_var,
            state="readonly",
            width=12,
        )
        self.table_scd_mode_combo.grid(row=3, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(props, text="SCD tracked columns (comma):").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        self.table_scd_tracked_entry = ttk.Entry(props, textvariable=self.table_scd_tracked_columns_var)
        self.table_scd_tracked_entry.grid(row=4, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(props, text="SCD active from column:").grid(row=5, column=0, sticky="w", padx=6, pady=6)
        self.table_scd_active_from_entry = ttk.Entry(props, textvariable=self.table_scd_active_from_var)
        self.table_scd_active_from_entry.grid(row=5, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(props, text="SCD active to column:").grid(row=6, column=0, sticky="w", padx=6, pady=6)
        self.table_scd_active_to_entry = ttk.Entry(props, textvariable=self.table_scd_active_to_var)
        self.table_scd_active_to_entry.grid(row=6, column=1, sticky="ew", padx=6, pady=6)

        self.apply_table_btn = ttk.Button(props, text="Apply table changes", command=self._apply_table_changes)
        self.apply_table_btn.grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=(10, 0))

        # Column editor (grid inside col)
        col = ttk.LabelFrame(right, text="Add column", padding=10)
        col.pack(fill="x", pady=(10, 0))
        col.columnconfigure(1, weight=1)

        ttk.Label(col, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.col_name_entry = ttk.Entry(col, textvariable=self.col_name_var)
        self.col_name_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Type:").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        self.col_dtype_combo = ttk.Combobox(
            col, values=DTYPES, textvariable=self.col_dtype_var, state="readonly", width=12
        )
        self.col_dtype_combo.grid(row=0, column=3, padx=6, pady=6)

        self.col_nullable_chk = ttk.Checkbutton(col, text="Nullable", variable=self.col_nullable_var)
        self.col_nullable_chk.grid(row=1, column=0, sticky="w", padx=6, pady=6)

        self.col_pk_chk = ttk.Checkbutton(col, text="Primary key (int only)", variable=self.col_pk_var)
        self.col_pk_chk.grid(row=1, column=1, sticky="w", padx=6, pady=6)

        self.col_unique_chk = ttk.Checkbutton(col, text="Unique", variable=self.col_unique_var)
        self.col_unique_chk.grid(row=1, column=2, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Min:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.col_min_entry = ttk.Entry(col, textvariable=self.col_min_var, width=12)
        self.col_min_entry.grid(row=2, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Max:").grid(row=2, column=2, sticky="w", padx=6, pady=6)
        self.col_max_entry = ttk.Entry(col, textvariable=self.col_max_var, width=12)
        self.col_max_entry.grid(row=2, column=3, sticky="w", padx=6, pady=6)

        ttk.Label(col, text="Choices (comma):").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        self.col_choices_entry = ttk.Entry(col, textvariable=self.col_choices_var)
        self.col_choices_entry.grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Regex pattern:").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        self.col_pattern_entry = ttk.Entry(col, textvariable=self.col_pattern_var)
        self.col_pattern_entry.grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=6)



        ttk.Label(col, text="Generator:").grid(row=5, column=0, sticky="w", padx=6, pady=6)
        self.col_generator_combo = ttk.Combobox(col, values=GENERATORS, textvariable=self.col_generator_var, state="readonly")
        self.col_generator_combo.grid(row=5, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(col, text="Params (JSON):").grid(row=6, column=0, sticky="w", padx=6, pady=6)
        self.col_params_entry = ttk.Entry(col, textvariable=self.col_params_var)
        self.col_params_entry.grid(row=6, column=1, columnspan=3, sticky="ew", padx=6, pady=6)
        #Adds Column
        self.add_col_btn = ttk.Button(col, text="Add column to selected table", command=self._add_column)
        self.add_col_btn.grid(row=8, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 0))

        #Correlation stuff
        ttk.Label(col, text="Depends on (comma):").grid(row=7, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(col, textvariable=self.col_depends_var).grid(row=7, column=1, columnspan=3, sticky="ew", padx=6, pady=6)
        dep_s = self.col_depends_var.get().strip()
        depends = [d.strip() for d in dep_s.split(",") if d.strip()] if dep_s else None


        # Columns table (pack inside cols_frame)
        cols_frame = ttk.LabelFrame(right, text="Columns", padding=8)
        cols_frame.pack(fill="both", expand=True, pady=(10, 0))

        cols = ("name", "dtype", "nullable", "pk", "unique", "min", "max", "choices", "pattern")
        self.columns_tree = ttk.Treeview(cols_frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.columns_tree.heading(c, text=c)
            self.columns_tree.column(c, width=110, anchor="w", stretch=True)
        self.columns_tree.column("name", width=140)
        self.columns_tree.column("choices", width=180)
        self.columns_tree.column("pattern", width=180)

        yscroll = ttk.Scrollbar(cols_frame, orient="vertical", command=self.columns_tree.yview)
        self.columns_tree.configure(yscrollcommand=yscroll.set)

        self.columns_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        col_actions = ttk.Frame(right)
        col_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(col_actions, text="Remove selected column", command=self._remove_selected_column).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(col_actions, text="Move up", command=lambda: self._move_selected_column(-1)).pack(side="left", padx=6)
        ttk.Button(col_actions, text="Move down", command=lambda: self._move_selected_column(1)).pack(side="left", padx=6)

        # ---- Right: relationships editor (grid/pack inside rel)
        rel_section = CollapsibleSection(main, title="Relationships (FKs)")
        rel_section.grid(row=0, column=2, sticky="nsew")
        rel = ttk.LabelFrame(rel_section.content, text="", padding=10)
        rel.pack(fill="both", expand=True)
        rel.columnconfigure(1, weight=1)
        rel.rowconfigure(6, weight=1)

        ttk.Label(rel, text="Parent table:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.fk_parent_combo = ttk.Combobox(rel, textvariable=self.fk_parent_table_var, state="readonly")
        self.fk_parent_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        self.fk_parent_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_fk_defaults())

        ttk.Label(rel, text="Child table:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.fk_child_combo = ttk.Combobox(rel, textvariable=self.fk_child_table_var, state="readonly")
        self.fk_child_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        self.fk_child_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_fk_defaults())

        ttk.Label(rel, text="Child FK column (int):").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.fk_child_col_combo = ttk.Combobox(rel, textvariable=self.fk_child_column_var, state="readonly")
        self.fk_child_col_combo.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(rel, text="Min children:").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(rel, textvariable=self.fk_min_children_var, width=8).grid(row=3, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(rel, text="Max children:").grid(row=4, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(rel, textvariable=self.fk_max_children_var, width=8).grid(row=4, column=1, sticky="w", padx=6, pady=6)

        self.add_fk_btn = ttk.Button(rel, text="Add relationship", command=self._add_fk)
        self.add_fk_btn.grid(row=5, column=0, columnspan=2, sticky="ew", padx=6, pady=(10, 8))

        fk_frame = ttk.LabelFrame(rel, text="Defined relationships", padding=8)
        fk_frame.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=6, pady=(6, 0))
        fk_frame.rowconfigure(0, weight=1)
        fk_frame.columnconfigure(0, weight=1)

        fk_cols = ("parent", "parent_pk", "child", "child_fk", "min", "max")
        self.fks_tree = ttk.Treeview(fk_frame, columns=fk_cols, show="headings", height=10)
        for c in fk_cols:
            self.fks_tree.heading(c, text=c)
            self.fks_tree.column(c, width=110, anchor="w", stretch=True)
        self.fks_tree.column("parent", width=110)
        self.fks_tree.column("child", width=110)
        self.fks_tree.column("parent_pk", width=90)
        self.fks_tree.column("child_fk", width=90)
        self.fks_tree.column("min", width=60, anchor="e")
        self.fks_tree.column("max", width=60, anchor="e")

        y2 = ttk.Scrollbar(fk_frame, orient="vertical", command=self.fks_tree.yview)
        self.fks_tree.configure(yscrollcommand=y2.set)

        self.fks_tree.grid(row=0, column=0, sticky="nsew")
        y2.grid(row=0, column=1, sticky="ns")

        self.remove_fk_btn = ttk.Button(rel, text="Remove selected relationship", command=self._remove_selected_fk)
        self.remove_fk_btn.grid(row=7, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 0))

        # =========================
        # Bottom: Generate / Preview / Export / SQLite
        # (pack bottom; grid inside bottom)
        # =========================
        bottom_section = CollapsibleSection(root, title="Generate / Preview / Export / SQLite")
        bottom_section.pack(fill="both", expand=True, pady=(12, 0))

        bottom = ttk.LabelFrame(bottom_section.content, text="", padding=12)
        bottom.pack(fill="both", expand=True)

        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(3, weight=1)

        ttk.Label(bottom, text="SQLite DB path:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(bottom, textvariable=self.db_path_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(bottom, text="Browse…", command=self._browse_db_path).grid(row=0, column=2, padx=6, pady=6)

        ttk.Label(bottom, text="Export format:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.export_option_combo = ttk.Combobox(
            bottom,
            values=EXPORT_OPTIONS,
            textvariable=self.export_option_var,
            state="readonly",
        )
        self.export_option_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        actions = ttk.Frame(bottom)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 10))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        actions.columnconfigure(3, weight=1)

        self.generate_btn = ttk.Button(actions, text="Generate data (all tables)", command=self._on_generate_project)
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=4)

        self.export_btn = ttk.Button(actions, text="Export data", command=self._on_export_data)
        self.export_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.sample_btn = ttk.Button(actions, text="Generate sample (10 rows/table)", command=self._on_generate_sample)
        self.sample_btn.grid(row=0, column=2, sticky="ew", padx=4)

        self.clear_btn = ttk.Button(actions, text="Clear generated data", command=self._clear_generated)
        self.clear_btn.grid(row=0, column=3, sticky="ew", padx=4)

        preview_area = ttk.Frame(bottom)
        preview_area.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
        preview_area.columnconfigure(1, weight=1)
        preview_area.rowconfigure(0, weight=1)

        left_preview = ttk.LabelFrame(preview_area, text="Preview", padding=10)
        left_preview.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left_preview.columnconfigure(0, weight=1)

        ttk.Label(left_preview, text="Table:").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.preview_table_combo = ttk.Combobox(left_preview, textvariable=self.preview_table_var, state="readonly")
        self.preview_table_combo.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.preview_table_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())

        ttk.Label(left_preview, text="Max rows to show:").grid(row=2, column=0, sticky="w")
        self.preview_limit_var = tk.StringVar(value="200")
        ttk.Entry(left_preview, textvariable=self.preview_limit_var, width=10).grid(row=3, column=0, sticky="w", pady=(0, 10))

        self.preview_btn = ttk.Button(left_preview, text="Refresh preview", command=self._refresh_preview)
        self.preview_btn.grid(row=4, column=0, sticky="ew")

        self.progress = ttk.Progressbar(left_preview, mode="indeterminate")
        self.progress.grid(row=5, column=0, sticky="ew", pady=(14, 0))

        right_preview = ttk.LabelFrame(preview_area, text="Data preview", padding=8)
        right_preview.grid(row=0, column=1, sticky="nsew")
        right_preview.rowconfigure(0, weight=1)
        right_preview.columnconfigure(0, weight=1)

        self.preview_tree = ttk.Treeview(right_preview, show="headings")
        y3 = ttk.Scrollbar(right_preview, orient="vertical", command=self.preview_tree.yview)
        x3 = ttk.Scrollbar(right_preview, orient="horizontal", command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=y3.set, xscrollcommand=x3.set)

        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        y3.grid(row=0, column=1, sticky="ns")
        x3.grid(row=1, column=0, sticky="ew")

        # Status line (pack on root)
        ttk.Label(root, textvariable=self.status_var).pack(anchor="w", pady=(10, 0))


    # ---------------- Helpers ----------------
    def _set_table_editor_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED

        self.table_name_entry.configure(state=state)
        self.row_count_entry.configure(state=state)
        self.table_business_key_entry.configure(state=state)
        self.table_scd_mode_combo.configure(state=("readonly" if enabled else tk.DISABLED))
        self.table_scd_tracked_entry.configure(state=state)
        self.table_scd_active_from_entry.configure(state=state)
        self.table_scd_active_to_entry.configure(state=state)
        self.apply_table_btn.configure(state=state)

        self.col_name_entry.configure(state=state)
        self.col_dtype_combo.configure(state=("readonly" if enabled else tk.DISABLED))
        self.col_nullable_chk.configure(state=state)
        self.col_pk_chk.configure(state=state)
        self.col_unique_chk.configure(state=state)
        self.col_min_entry.configure(state=state)
        self.col_max_entry.configure(state=state)
        self.col_choices_entry.configure(state=state)
        self.col_pattern_entry.configure(state=state)
        self.add_col_btn.configure(state=state)

    def _refresh_tables_list(self) -> None:
        self.tables_list.delete(0, tk.END)
        for t in self.project.tables:
            self.tables_list.insert(tk.END, t.table_name)

    def _refresh_columns_tree(self) -> None:
        for item in self.columns_tree.get_children():
            self.columns_tree.delete(item)

        if self.selected_table_index is None:
            return

        t = self.project.tables[self.selected_table_index]
        for i, c in enumerate(t.columns):
            self.columns_tree.insert(
                "",
                tk.END,
                values=(
                    c.name, c.dtype, c.nullable, c.primary_key, c.unique,
                    c.min_value, c.max_value,
                    ", ".join(c.choices) if c.choices else "",
                    c.pattern or "",
                ),
                tags=(str(i),),
            )

    def _selected_column_index(self) -> int | None:
        sel = self.columns_tree.selection()
        if not sel:
            return None
        return int(self.columns_tree.item(sel[0], "tags")[0])

    def _parse_column_name_csv(
        self,
        raw_value: str,
        *,
        location: str,
        field_name: str,
    ) -> list[str] | None:
        value = raw_value.strip()
        if value == "":
            return None
        names = [part.strip() for part in value.split(",")]
        if any(name == "" for name in names):
            raise ValueError(
                f"{location}: {field_name} contains an empty column name. "
                "Fix: remove extra commas and provide comma-separated column names."
            )
        if len(set(names)) != len(names):
            raise ValueError(
                f"{location}: {field_name} contains duplicate column names. "
                "Fix: list each column only once."
            )
        return names

    def _parse_optional_column_name(
        self,
        raw_value: str,
        *,
        location: str,
        field_name: str,
    ) -> str | None:
        value = raw_value.strip()
        if value == "":
            return None
        if "," in value:
            raise ValueError(
                f"{location}: {field_name} must contain exactly one column name. "
                f"Fix: provide one name or leave {field_name} empty."
            )
        return value

    def _apply_project_vars_to_model(self) -> None:
        name = self.project_name_var.get().strip()
        seed = int(self.seed_var.get().strip())
        self.project = SchemaProject(
            name=name,
            seed=seed,
            tables=self.project.tables,
            foreign_keys=self.project.foreign_keys,
        )

    # ----- FK helpers -----
    def _table_pk_name(self, table_name: str) -> str:
        for t in self.project.tables:
            if t.table_name == table_name:
                for c in t.columns:
                    if c.primary_key:
                        return c.name
        raise ValueError(f"Table '{table_name}' has no primary key (should not happen).")

    def _int_columns(self, table_name: str) -> list[str]:
        for t in self.project.tables:
            if t.table_name == table_name:
                return [c.name for c in t.columns if c.dtype == "int"]
        return []

    def _refresh_fk_dropdowns(self) -> None:
        names = [t.table_name for t in self.project.tables]

        self.fk_parent_combo["values"] = names
        self.fk_child_combo["values"] = names

        if names:
            if not self.fk_parent_table_var.get():
                self.fk_parent_table_var.set(names[0])
            if not self.fk_child_table_var.get():
                self.fk_child_table_var.set(names[0])

        self._sync_fk_defaults()

    def _sync_fk_defaults(self) -> None:
        child = self.fk_child_table_var.get().strip()
        if not child:
            self.fk_child_col_combo["values"] = []
            self.fk_child_column_var.set("")
            return

        int_cols = self._int_columns(child)
        self.fk_child_col_combo["values"] = int_cols

        pk = ""
        try:
            pk = self._table_pk_name(child)
        except Exception:
            pk = ""

        preferred = ""
        for c in int_cols:
            if c != pk and c.endswith("_id"):
                preferred = c
                break

        if preferred:
            self.fk_child_column_var.set(preferred)
        elif int_cols:
            non_pk = [c for c in int_cols if c != pk]
            self.fk_child_column_var.set(non_pk[0] if non_pk else int_cols[0])
        else:
            self.fk_child_column_var.set("")

    def _refresh_fks_tree(self) -> None:
        for item in self.fks_tree.get_children():
            self.fks_tree.delete(item)

        for i, fk in enumerate(self.project.foreign_keys):
            self.fks_tree.insert(
                "",
                tk.END,
                values=(fk.parent_table, fk.parent_column, fk.child_table, fk.child_column, fk.min_children, fk.max_children),
                tags=(str(i),),
            )

    def _selected_fk_index(self) -> int | None:
        sel = self.fks_tree.selection()
        if not sel:
            return None
        return int(self.fks_tree.item(sel[0], "tags")[0])

    # ---------------- Table list actions ----------------
    def _add_table(self) -> None:
        try:
            self._apply_project_vars_to_model()
            base_name = "new_table"
            existing = {t.table_name for t in self.project.tables}
            n = 1
            name = base_name
            while name in existing:
                n += 1
                name = f"{base_name}_{n}"

            new_table = TableSpec(
                table_name=name,
                row_count=100,
                columns=[
                    ColumnSpec(name=f"{name}_id", dtype="int", nullable=False, primary_key=True),
                ],
            )

            tables = list(self.project.tables) + [new_table]
            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_tables_list()

            self.selected_table_index = len(self.project.tables) - 1
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(self.selected_table_index)
            self.tables_list.activate(self.selected_table_index)
            self._load_selected_table_into_editor()

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set(f"Added table '{name}'.")
        except Exception as exc:
            messagebox.showerror("Add table failed", str(exc))
        self._run_validation()


    def _validate_project_detailed(self, project: SchemaProject) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        # Use existing validator (throws on first error)
        try:
            validate_project(project)
        except Exception as exc:
            issues.append(ValidationIssue("error", "project", None, None, str(exc)))

        # Per-table checks
        for t in project.tables:
            # Must have PK
            if not any(c.primary_key for c in t.columns):
                issues.append(ValidationIssue("error", "table", t.table_name, None, "Table has no primary key."))

            # Duplicate column names
            names = [c.name for c in t.columns]
            if len(names) != len(set(names)):
                issues.append(ValidationIssue("error", "table", t.table_name, None, "Duplicate column names."))

            # Warn on nullable PK
            for c in t.columns:
                if c.primary_key and c.nullable:
                    issues.append(ValidationIssue("warn", "column", t.table_name, c.name, "Primary key should not be nullable."))

            # Warn on text PK (even if model prevents it)
            for c in t.columns:
                if c.primary_key and c.dtype != "int":
                    issues.append(ValidationIssue("warn", "column", t.table_name, c.name, "Primary key is not int (recommended int)."))

            # Direction 3 compatibility warning: float is still supported but deprecated for new authoring.
            for c in t.columns:
                if c.dtype == "float":
                    issues.append(
                        ValidationIssue(
                            "warn",
                            "column",
                            t.table_name,
                            c.name,
                            "Column uses legacy dtype 'float'. Fix: prefer dtype='decimal' for new columns.",
                        )
                    )

        # FK checks
        for fk in project.foreign_keys:
            # parent must exist
            if fk.parent_table not in [t.table_name for t in project.tables]:
                issues.append(ValidationIssue("error", "fk", fk.child_table, fk.child_column, f"Parent table '{fk.parent_table}' not found."))

            # child must exist
            if fk.child_table not in [t.table_name for t in project.tables]:
                issues.append(ValidationIssue("error", "fk", fk.child_table, fk.child_column, f"Child table '{fk.child_table}' not found."))

            if fk.min_children > fk.max_children:
                issues.append(ValidationIssue("error", "fk", fk.child_table, fk.child_column, "FK min_children > max_children."))

        return issues

    def _run_validation(self) -> None:
        try:
            self._apply_project_vars_to_model()
        except Exception as exc:
            messagebox.showerror("Project error", str(exc))
            return

        issues = self._validate_project_detailed(self.project)

        # Define checks (columns in the heatmap)
        checks = ["PK", "Columns", "FKs", "Generator"]
        tables = [t.table_name for t in self.project.tables]

        # Default OK everywhere
        status: dict[tuple[str, str], str] = {(t, c): "ok" for t in tables for c in checks}
        details: dict[tuple[str, str], list[str]] = {}

        def mark(table: str, check: str, sev: str, msg: str) -> None:
            key = (table, check)
            # escalate: ok < warn < error
            rank = {"ok": 0, "warn": 1, "error": 2}
            if rank[sev] > rank[status.get(key, "ok")]:
                status[key] = sev
            details.setdefault(key, []).append(msg)

        # Map issues into heatmap buckets
        for iss in issues:
            if iss.table is None:
                continue
            if iss.scope in ("table", "column"):
                # PK + Columns buckets
                if "primary key" in iss.message.lower() or "pk" in iss.message.lower():
                    mark(iss.table, "PK", iss.severity, iss.message)
                else:
                    mark(iss.table, "Columns", iss.severity, iss.message)
            elif iss.scope == "fk":
                mark(iss.table, "FKs", iss.severity, iss.message)
            else:
                mark(iss.table, "Generator", iss.severity, iss.message)


        # Update heatmap
        self.heatmap.set_data(tables=tables, checks=checks, status=status, details=details)

        # Summary
        e = sum(1 for i in issues if i.severity == "error")
        w = sum(1 for i in issues if i.severity == "warn")
        self.last_validation_errors = e
        self.last_validation_warnings = w
        self.validation_summary_var.set(f"Validation: {e} errors, {w} warnings. Click cells for details.")
        self._update_generate_enabled()

    def _on_generate_project(self) -> None:
        if self.last_validation_errors > 0:
            messagebox.showerror("Cannot generate", "Schema has validation errors. Fix them first.")
            return
        ...


    def _remove_table(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            idx = self.selected_table_index
            removed = self.project.tables[idx].table_name

            # remove any FK where this table is parent or child
            fks = [fk for fk in self.project.foreign_keys if fk.parent_table != removed and fk.child_table != removed]

            tables = list(self.project.tables)
            tables.pop(idx)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self.selected_table_index = None
            self._refresh_tables_list()
            self._refresh_columns_tree()
            self._set_table_editor_enabled(False)

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set(f"Removed table '{removed}'.")
        except Exception as exc:
            messagebox.showerror("Remove table failed", str(exc))

        self._run_validation()


    def _on_table_selected(self, _event=None) -> None:
        sel = self.tables_list.curselection()
        if not sel:
            self.selected_table_index = None
            self._set_table_editor_enabled(False)
            self._refresh_columns_tree()
            return
        self.selected_table_index = int(sel[0])
        self._load_selected_table_into_editor()

    def _load_selected_table_into_editor(self) -> None:
        if self.selected_table_index is None:
            return
        t = self.project.tables[self.selected_table_index]
        self.table_name_var.set(t.table_name)
        self.row_count_var.set(str(t.row_count))
        self.table_business_key_var.set(", ".join(t.business_key) if t.business_key else "")
        self.table_scd_mode_var.set((t.scd_mode or "").strip().lower())
        self.table_scd_tracked_columns_var.set(", ".join(t.scd_tracked_columns) if t.scd_tracked_columns else "")
        self.table_scd_active_from_var.set(t.scd_active_from_column or "")
        self.table_scd_active_to_var.set(t.scd_active_to_column or "")
        self._set_table_editor_enabled(True)
        self._refresh_columns_tree()

    def _apply_table_changes(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            self._apply_project_vars_to_model()

            idx = self.selected_table_index
            old = self.project.tables[idx]

            new_name = self.table_name_var.get().strip()
            if not new_name:
                raise ValueError("Table name cannot be empty.")

            row_count = int(self.row_count_var.get().strip())
            location = f"Table '{new_name}' / Table editor"
            business_key = self._parse_column_name_csv(
                self.table_business_key_var.get(),
                location=location,
                field_name="business_key",
            )
            scd_mode_raw = self.table_scd_mode_var.get().strip().lower()
            if scd_mode_raw not in {"", "scd1", "scd2"}:
                raise ValueError(
                    f"{location}: unsupported scd_mode '{self.table_scd_mode_var.get()}'. "
                    "Fix: choose 'scd1', 'scd2', or leave it empty."
                )
            scd_mode = scd_mode_raw or None
            scd_tracked_columns = self._parse_column_name_csv(
                self.table_scd_tracked_columns_var.get(),
                location=location,
                field_name="scd_tracked_columns",
            )
            scd_active_from_column = self._parse_optional_column_name(
                self.table_scd_active_from_var.get(),
                location=location,
                field_name="scd_active_from_column",
            )
            scd_active_to_column = self._parse_optional_column_name(
                self.table_scd_active_to_var.get(),
                location=location,
                field_name="scd_active_to_column",
            )
            
            ## We now allow for auto-sizing of children
            # if row_count <= 0:
            #     raise ValueError("Row count must be > 0.")

            # rename references in existing foreign keys
            fks = []
            for fk in self.project.foreign_keys:
                fks.append(
                    ForeignKeySpec(
                        child_table=(new_name if fk.child_table == old.table_name else fk.child_table),
                        child_column=fk.child_column,
                        parent_table=(new_name if fk.parent_table == old.table_name else fk.parent_table),
                        parent_column=fk.parent_column,
                        min_children=fk.min_children,
                        max_children=fk.max_children,
                    )
                )

            tables = list(self.project.tables)
            tables[idx] = TableSpec(
                table_name=new_name,
                columns=old.columns,
                row_count=row_count,
                business_key=business_key,
                scd_mode=scd_mode,
                scd_tracked_columns=scd_tracked_columns,
                scd_active_from_column=scd_active_from_column,
                scd_active_to_column=scd_active_to_column,
            )

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_tables_list()
            self.tables_list.selection_clear(0, tk.END)
            self.tables_list.selection_set(idx)

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set("Applied table changes.")
        except Exception as exc:
            messagebox.showerror("Apply failed", str(exc))

        self._run_validation()


    # ---------------- Column actions ----------------
    def _add_column(self) -> None:
        if self.selected_table_index is None:
            return
        try:
            self._apply_project_vars_to_model()
            idx = self.selected_table_index
            t = self.project.tables[idx]

            name = self.col_name_var.get().strip()
            dtype = self.col_dtype_var.get().strip()

            if dtype == "float":
                raise ValueError(
                    "Add column / Type: dtype 'float' is deprecated for new GUI columns. "
                    "Fix: choose dtype='decimal' for new columns; keep legacy float only in loaded JSON."
                )
            if dtype not in DTYPES:
                allowed = ", ".join(DTYPES)
                raise ValueError(
                    f"Add column / Type: unsupported dtype '{dtype}'. "
                    f"Fix: choose one of: {allowed}."
                )

            gen_name = self.col_generator_var.get().strip() or None

            params_text = self.col_params_var.get().strip()
            params = None
            if params_text:
                try:
                    obj = json.loads(params_text)
                    if not isinstance(obj, dict):
                        raise ValueError("Params JSON must be an object/dict, e.g. {\"path\": \"...\", \"column_index\": 0}")
                    params = obj
                except Exception as exc:
                    raise ValueError(f"Params JSON invalid: {exc}") from exc


            if not name:
                raise ValueError("Column name cannot be empty.")

            nullable = bool(self.col_nullable_var.get())
            pk = bool(self.col_pk_var.get())
            unique = bool(self.col_unique_var.get())

            min_s = self.col_min_var.get().strip()
            max_s = self.col_max_var.get().strip()
            min_v = float(min_s) if min_s != "" else None
            max_v = float(max_s) if max_s != "" else None

            choices_s = self.col_choices_var.get().strip()
            choices = [c.strip() for c in choices_s.split(",") if c.strip()] if choices_s else None

            pattern = self.col_pattern_var.get().strip() or None

            new_col = ColumnSpec(
                    name=name,
                    dtype=dtype,
                    nullable=nullable,
                    primary_key=pk,
                    unique=unique,
                    min_value=min_v,
                    max_value=max_v,
                    choices=choices,
                    pattern=pattern,

                    generator=gen_name,
                    params=params,
                )

            self.col_generator_var.set("")
            self.col_params_var.set("")


            cols = list(t.columns)

            if any(c.name == new_col.name for c in cols):
                raise ValueError(f"Column '{new_col.name}' already exists on table '{t.table_name}'.")

            # If setting PK, unset existing PK (MVP allows only one PK)
            if new_col.primary_key:
                if new_col.dtype != "int":
                    raise ValueError("Primary key must be dtype=int in this MVP.")
                cols = [ColumnSpec(**{**c.__dict__, "primary_key": False}) for c in cols]  # type: ignore

            cols.append(new_col)

            tables = list(self.project.tables)
            tables[idx] = TableSpec(
                table_name=t.table_name,
                columns=cols,
                row_count=t.row_count,
                business_key=t.business_key,
                scd_mode=t.scd_mode,
                scd_tracked_columns=t.scd_tracked_columns,
                scd_active_from_column=t.scd_active_from_column,
                scd_active_to_column=t.scd_active_to_column,
            )

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project

            # clear form
            self.col_name_var.set("")
            self.col_min_var.set("")
            self.col_max_var.set("")
            self.col_choices_var.set("")
            self.col_pattern_var.set("")
            self.col_pk_var.set(False)

            self._refresh_columns_tree()
            self._refresh_fk_dropdowns()

            self.status_var.set("Column added.")
        except Exception as exc:
            messagebox.showerror("Add column failed", str(exc))
        self._run_validation()

    def _remove_selected_column(self) -> None:
        if self.selected_table_index is None:
            return
        col_idx = self._selected_column_index()
        if col_idx is None:
            return
        try:
            self._apply_project_vars_to_model()
            t_idx = self.selected_table_index
            t = self.project.tables[t_idx]

            cols = list(t.columns)
            removed = cols[col_idx].name

            # prevent removing a column that is used in an FK
            for fk in self.project.foreign_keys:
                if fk.child_table == t.table_name and fk.child_column == removed:
                    raise ValueError("Cannot remove: column is used as a child FK.")
                if fk.parent_table == t.table_name and fk.parent_column == removed:
                    raise ValueError("Cannot remove: column is used as a parent PK reference in an FK.")

            cols.pop(col_idx)

            tables = list(self.project.tables)
            tables[t_idx] = TableSpec(
                table_name=t.table_name,
                columns=cols,
                row_count=t.row_count,
                business_key=t.business_key,
                scd_mode=t.scd_mode,
                scd_tracked_columns=t.scd_tracked_columns,
                scd_active_from_column=t.scd_active_from_column,
                scd_active_to_column=t.scd_active_to_column,
            )

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_columns_tree()
            self._refresh_fk_dropdowns()
            self.status_var.set(f"Removed column '{removed}'.")
        except Exception as exc:
            messagebox.showerror("Remove column failed", str(exc))
        self._run_validation()

    def _move_selected_column(self, delta: int) -> None:
        if self.selected_table_index is None:
            return
        col_idx = self._selected_column_index()
        if col_idx is None:
            return
        try:
            self._apply_project_vars_to_model()
            t_idx = self.selected_table_index
            t = self.project.tables[t_idx]

            new_idx = col_idx + delta
            if new_idx < 0 or new_idx >= len(t.columns):
                return

            cols = list(t.columns)
            cols[col_idx], cols[new_idx] = cols[new_idx], cols[col_idx]

            tables = list(self.project.tables)
            tables[t_idx] = TableSpec(
                table_name=t.table_name,
                columns=cols,
                row_count=t.row_count,
                business_key=t.business_key,
                scd_mode=t.scd_mode,
                scd_tracked_columns=t.scd_tracked_columns,
                scd_active_from_column=t.scd_active_from_column,
                scd_active_to_column=t.scd_active_to_column,
            )

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=tables,
                foreign_keys=self.project.foreign_keys,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_columns_tree()
            self._refresh_fk_dropdowns()

            children = self.columns_tree.get_children()
            if 0 <= new_idx < len(children):
                self.columns_tree.selection_set(children[new_idx])

        except Exception as exc:
            messagebox.showerror("Move column failed", str(exc))
        self._run_validation()

    # ---------------- Relationship actions ----------------
    def _add_fk(self) -> None:
        try:
            self._apply_project_vars_to_model()

            parent = self.fk_parent_table_var.get().strip()
            child = self.fk_child_table_var.get().strip()
            child_col = self.fk_child_column_var.get().strip()

            if not parent or not child or not child_col:
                raise ValueError("Choose parent table, child table, and child FK column.")

            if parent == child:
                raise ValueError("Parent table and child table must be different.")

            parent_pk = self._table_pk_name(parent)
            child_pk = self._table_pk_name(child)

            min_k = int(self.fk_min_children_var.get().strip())
            max_k = int(self.fk_max_children_var.get().strip())
            if min_k <= 0 or max_k <= 0:
                raise ValueError("Min/max children must be > 0.")
            if min_k > max_k:
                raise ValueError("Min children cannot exceed max children.")

            # # MVP constraint: child can only have one FK
            # if any(fk.child_table == child for fk in self.project.foreign_keys):
            #     raise ValueError(f"Table '{child}' already has a foreign key (MVP supports 1 FK per child table).")

            if child_col == child_pk:
                raise ValueError("Child FK column cannot be the child's primary key column.")

            if child_col not in self._int_columns(child):
                raise ValueError("Child FK column must be an int column.")
            
            # A child column can only be used by one FK
            if any(fk.child_table == child and fk.child_column == child_col for fk in self.project.foreign_keys):
                raise ValueError(f"Column '{child}.{child_col}' is already used as a foreign key.")


            fks = list(self.project.foreign_keys)
            fks.append(
                ForeignKeySpec(
                    child_table=child,
                    child_column=child_col,
                    parent_table=parent,
                    parent_column=parent_pk,
                    min_children=min_k,
                    max_children=max_k,
                )
            )

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=self.project.tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_fks_tree()
            self.status_var.set("Relationship added.")
        except Exception as exc:
            messagebox.showerror("Add relationship failed", str(exc))
        self._run_validation()

    def _remove_selected_fk(self) -> None:
        idx = self._selected_fk_index()
        if idx is None:
            return
        try:
            self._apply_project_vars_to_model()

            fks = list(self.project.foreign_keys)
            removed = fks[idx]
            fks.pop(idx)

            new_project = SchemaProject(
                name=self.project.name,
                seed=self.project.seed,
                tables=self.project.tables,
                foreign_keys=fks,
            )
            validate_project(new_project)

            self.project = new_project
            self._refresh_fks_tree()
            self.status_var.set(
                f"Removed relationship: {removed.parent_table}.{removed.parent_column} → {removed.child_table}.{removed.child_column}"
            )
        except Exception as exc:
            messagebox.showerror("Remove relationship failed", str(exc))
        self._run_validation()

    def _browse_db_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose SQLite database file",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path_var.set(path)
    def _set_running(self, running: bool, msg: str) -> None:
        self.is_running = running
        self.status_var.set(msg)
        if running:
            self.progress.start(10)
        else:
            self.progress.stop()

        # disable buttons while running
        state = tk.DISABLED if running else tk.NORMAL
        self.generate_btn.configure(state=state)
        self.export_btn.configure(state=state)
        self.export_option_combo.configure(state=("disabled" if running else "readonly"))
        self.clear_btn.configure(state=state)
        self.preview_btn.configure(state=state)

    def _on_generate_project(self) -> None:
        if self.is_running:
            return
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        self._set_running(True, "Generating data for all tables…")

        def work():
            try:
                rows = generate_project_rows(self.project)
                self.after(0, lambda: self._on_generated_ok(rows))
            except Exception as exc:
                logger.exception("Generation failed: %s", exc)
                msg = str(exc)
                self.after(0, lambda m=msg: self._on_job_failed(m))

        threading.Thread(target=work, daemon=True).start()

    def _on_generated_ok(self, rows: dict[str, list[dict[str, object]]]) -> None:
        self.generated_rows = rows
        self._set_running(False, "Generation complete.")

        # update preview table dropdown
        table_names = list(rows.keys())
        self.preview_table_combo["values"] = table_names
        if table_names:
            if not self.preview_table_var.get() or self.preview_table_var.get() not in table_names:
                self.preview_table_var.set(table_names[0])
            self._refresh_preview()

        # quick summary
        summary = "\n".join([f"{t}: {len(r)} rows" for t, r in rows.items()])
        messagebox.showinfo("Generated", f"Generated data:\n{summary}")
        self.status_var.set(f"Generated {sum(len(v) for v in rows.values())} rows across {len(rows)} tables.")


    def _refresh_preview(self) -> None:
        if not self.generated_rows:
            self._clear_preview_tree()
            return

        table = self.preview_table_var.get().strip()
        if not table or table not in self.generated_rows:
            self._clear_preview_tree()
            return

        try:
            limit = int(self.preview_limit_var.get().strip())
            if limit <= 0:
                raise ValueError
        except Exception:
            limit = 200
            self.preview_limit_var.set("200")

        rows = self.generated_rows[table][:limit]
        self._render_preview_rows(rows)

    def _clear_preview_tree(self) -> None:
        self.preview_tree["columns"] = ()
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

    def _render_preview_rows(self, rows: list[dict[str, object]]) -> None:
        self._clear_preview_tree()
        if not rows:
            return

        # Determine columns from keys of first row
        cols = list(rows[0].keys())
        self.preview_tree["columns"] = tuple(cols)

        for c in cols:
            self.preview_tree.heading(c, text=c)
            self.preview_tree.column(c, width=140, anchor="w", stretch=True)

        for r in rows:
            values = [r.get(c) for c in cols]
            self.preview_tree.insert("", tk.END, values=values)

    def _on_export_data(self) -> None:
        if self.is_running:
            return

        try:
            export_option = validate_export_option(self.export_option_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid export option", str(exc))
            return

        if export_option == EXPORT_OPTION_CSV:
            self._on_export_csv()
            return
        if export_option == EXPORT_OPTION_SQLITE:
            self._on_create_insert_sqlite()
            return

        # Defensive fallback: export options are validated above.
        messagebox.showerror(
            "Invalid export option",
            f"Unsupported export option '{export_option}'. Fix: choose a supported export option.",
        )

    def _on_export_csv(self) -> None:
        if self.is_running:
            return
        if not self.generated_rows:
            messagebox.showwarning("Nothing to export", "Generate data first.")
            return

        folder = filedialog.askdirectory(title="Choose a folder to export CSVs into")
        if not folder:
            return

        try:
            for table, rows in self.generated_rows.items():
                if not rows:
                    continue
                path = os.path.join(folder, f"{table}.csv")
                cols = list(rows[0].keys())

                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(cols)
                    for r in rows:
                        w.writerow([r.get(c) for c in cols])

            self.status_var.set(f"Exported CSVs to: {folder}")
            messagebox.showinfo("Export complete", f"Exported one CSV per table into:\n{folder}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _on_create_insert_sqlite(self) -> None:
        if self.is_running:
            return
        if not self.generated_rows:
            messagebox.showwarning("No data", "Generate data first.")
            return

        db_path = self.db_path_var.get().strip()
        if not db_path:
            messagebox.showerror("Missing DB path", "Please choose a SQLite DB path.")
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        self._set_running(True, "Creating tables and inserting rows into SQLite…")

        def work():
            try:
                create_tables(db_path, self.project)
                counts = insert_project_rows(db_path, self.project, self.generated_rows, chunk_size=5000)
                self.after(0, lambda: self._on_sqlite_ok(db_path, counts))
            except Exception as exc:
                logger.exception("SQLite insert failed: %s", exc)
                msg = str(exc)
                self.after(0, lambda m=msg: self._on_job_failed(m))

        threading.Thread(target=work, daemon=True).start()

    def _on_sqlite_ok(self, db_path: str, counts: dict[str, int]) -> None:
        self._set_running(False, "SQLite insert complete.")
        summary = "\n".join([f"{t}: {n} inserted" for t, n in counts.items()])
        messagebox.showinfo("SQLite complete", f"Inserted into:\n{db_path}\n\n{summary}")

    def _clear_generated(self) -> None:
        self.generated_rows = {}
        self.preview_table_combo["values"] = []
        self.preview_table_var.set("")
        self._clear_preview_tree()
        self.status_var.set("Cleared generated data.")

    def _on_job_failed(self, msg: str) -> None:
        self._set_running(False, "Failed.")
        messagebox.showerror("Error", msg)

    def _update_generate_enabled(self) -> None:
        """
        Enable Generate buttons only when there are no validation errors.
        Note: when is_running=True we still disable controls via _set_running().
        """
        if getattr(self, "is_running", False):
            return  # _set_running handles it

        ok = (self.last_validation_errors == 0)

        # Your main generate button
        if hasattr(self, "generate_btn"):
            self.generate_btn.configure(state=(tk.NORMAL if ok else tk.DISABLED))

        # Sample generate button (we'll add this in polish 4)
        if hasattr(self, "sample_btn"):
            self.sample_btn.configure(state=(tk.NORMAL if ok else tk.DISABLED))

    def _make_sample_project(self, n: int = 10) -> SchemaProject:
        """
        Return a copy of the current project with root table row_counts set to n.
        Child tables keep their existing row_count (generator typically ignores it for child tables anyway).
        """
        child_tables = {fk.child_table for fk in self.project.foreign_keys}

        new_tables: list[TableSpec] = []
        for t in self.project.tables:
            rc = t.row_count
            if t.table_name not in child_tables:
                rc = n
            new_tables.append(
                TableSpec(
                    table_name=t.table_name,
                    row_count=rc,
                    columns=t.columns,
                    business_key=t.business_key,
                    scd_mode=t.scd_mode,
                    scd_tracked_columns=t.scd_tracked_columns,
                    scd_active_from_column=t.scd_active_from_column,
                    scd_active_to_column=t.scd_active_to_column,
                )
            )

        return SchemaProject(
            name=self.project.name,
            seed=self.project.seed,
            tables=new_tables,
            foreign_keys=self.project.foreign_keys,
        )

    def _on_generate_sample(self) -> None:
        if self.is_running:
            return

        if self.last_validation_errors > 0:
            messagebox.showerror("Cannot generate", "Schema has validation errors. Fix them first.")
            return

        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)
        except Exception as exc:
            messagebox.showerror("Invalid project", str(exc))
            return

        sample_project = self._make_sample_project(10)

        self._set_running(True, "Generating sample data (10 rows per root table)…")

        def work():
            try:
                rows = generate_project_rows(sample_project)
                self.after(0, lambda: self._on_generated_ok(rows))
            except Exception as exc:
                logger.exception("Sample generation failed: %s", exc)
                msg = str(exc)  # capture for Python 3.13 (exception var lifetime)
                self.after(0, lambda m=msg: self._on_job_failed(m))

        threading.Thread(target=work, daemon=True).start()



    # ---------------- Save / Load ----------------
    def _save_project(self) -> None:
        try:
            self._apply_project_vars_to_model()
            validate_project(self.project)

            path = filedialog.asksaveasfilename(
                title="Save project as JSON",
                defaultextension=".json",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            save_project_to_json(self.project, path)
            self.status_var.set(f"Saved project: {path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def _load_project(self) -> None:
        try:
            path = filedialog.askopenfilename(
                title="Load project JSON",
                filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            project = load_project_from_json(path)
            self.project = project
            self.project_name_var.set(project.name)
            self.seed_var.set(str(project.seed))

            self.selected_table_index = None
            self._refresh_tables_list()
            self._refresh_columns_tree()
            self._set_table_editor_enabled(False)

            self._refresh_fk_dropdowns()
            self._refresh_fks_tree()

            self.status_var.set(f"Loaded project: {path}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
