from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.run_models import coerce_execution_mode
from src.gui_kit.run_models import coerce_output_mode
from src.gui_kit.table_virtual import TableColumnSpec
from src.gui_kit.table_virtual import VirtualTableAdapter
from src.multiprocessing_runtime import EXECUTION_MODES
from src.performance_scaling import FK_CACHE_MODES
from src.performance_scaling import OUTPUT_MODES

__all__ = ["RunWorkflowCapabilities", "RunWorkflowSurface"]


@dataclass(frozen=True)
class RunWorkflowCapabilities:
    estimate: bool = False
    build_plan: bool = False
    benchmark: bool = False
    generate_strategy: bool = False
    start_run: bool = False
    start_fallback: bool = False
    workers_tab: bool = False
    failures_tab: bool = False
    history_tab: bool = False
    show_status_label: bool = True


class RunWorkflowSurface(ttk.Frame):
    """Shared run-workflow UI regions for v2 and classic screens."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        model: RunWorkflowViewModel,
        capabilities: RunWorkflowCapabilities,
        status_callback=None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.capabilities = capabilities
        self._status_callback = status_callback

        self.schema_path_var = tk.StringVar(value=model.schema_path)
        self.target_tables_var = tk.StringVar(value=model.target_tables)
        self.row_overrides_var = tk.StringVar(value=model.row_overrides_json)
        self.preview_row_target_var = tk.StringVar(value=model.preview_row_target)
        self.output_mode_var = tk.StringVar(value=coerce_output_mode(model.output_mode))
        self.chunk_size_rows_var = tk.StringVar(value=model.chunk_size_rows)
        self.preview_page_size_var = tk.StringVar(value=model.preview_page_size)
        self.sqlite_batch_size_var = tk.StringVar(value=model.sqlite_batch_size)
        self.csv_buffer_rows_var = tk.StringVar(value=model.csv_buffer_rows)
        self.fk_cache_mode_var = tk.StringVar(value=model.fk_cache_mode)
        self.strict_chunking_var = tk.BooleanVar(value=model.strict_deterministic_chunking)
        self.execution_mode_var = tk.StringVar(value=coerce_execution_mode(model.execution_mode))
        self.worker_count_var = tk.StringVar(value=model.worker_count)
        self.max_inflight_chunks_var = tk.StringVar(value=model.max_inflight_chunks)
        self.ipc_queue_size_var = tk.StringVar(value=model.ipc_queue_size)
        self.retry_limit_var = tk.StringVar(value=model.retry_limit)
        self.profile_name_var = tk.StringVar(value=model.profile_name)

        self.live_phase_var = tk.StringVar(value="Idle")
        self.live_rows_var = tk.StringVar(value="Rows processed: 0")
        self.live_eta_var = tk.StringVar(value="ETA: --")
        self.status_var = tk.StringVar(value="Ready.")
        self.inline_error_var = tk.StringVar(value="")
        self.next_action_var = tk.StringVar(value="")
        self._tab_row_counts: dict[str, int] = {}
        self._empty_hint_label_by_key: dict[str, ttk.Label] = {}

        self.columnconfigure(0, weight=1)

        self._build_config_card()
        self._build_progress_strip()
        self._build_results_workspace()
        self._build_status_region()
        self.schema_path_var.trace_add("write", self._on_schema_path_changed)
        self._refresh_guidance_hints()

    def _build_config_card(self) -> None:
        self.config_card = ttk.LabelFrame(self, text="Run Config", padding=10)
        self.config_card.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 6))
        for idx in (1, 3):
            self.config_card.columnconfigure(idx, weight=1)

        ttk.Label(self.config_card, text="Schema JSON").grid(row=0, column=0, sticky="w")
        self.schema_entry = ttk.Entry(self.config_card, textvariable=self.schema_path_var)
        self.schema_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8, 8))
        self.browse_btn = ttk.Button(self.config_card, text="Browse...")
        self.browse_btn.grid(row=0, column=4, sticky="ew", padx=(0, 8))
        self.load_schema_btn = ttk.Button(self.config_card, text="Load")
        self.load_schema_btn.grid(row=0, column=5, sticky="ew")

        ttk.Label(self.config_card, text="Target tables").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.target_tables_entry = ttk.Entry(self.config_card, textvariable=self.target_tables_var)
        self.target_tables_entry.grid(row=1, column=1, sticky="ew", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Row overrides JSON").grid(row=1, column=2, sticky="w", pady=(6, 0))
        self.row_overrides_entry = ttk.Entry(self.config_card, textvariable=self.row_overrides_var)
        self.row_overrides_entry.grid(row=1, column=3, columnspan=3, sticky="ew", padx=(8, 0), pady=(6, 0))

        ttk.Label(self.config_card, text="Output").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.output_mode_combo = ttk.Combobox(
            self.config_card,
            textvariable=self.output_mode_var,
            state="readonly",
            values=OUTPUT_MODES,
            width=12,
        )
        self.output_mode_combo.grid(row=2, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Execution mode").grid(row=2, column=2, sticky="w", pady=(6, 0))
        self.execution_mode_combo = ttk.Combobox(
            self.config_card,
            textvariable=self.execution_mode_var,
            state="readonly",
            values=EXECUTION_MODES,
            width=20,
        )
        self.execution_mode_combo.grid(row=2, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Profile").grid(row=2, column=4, sticky="w", pady=(6, 0))
        self.profile_name_entry = ttk.Entry(self.config_card, textvariable=self.profile_name_var, width=16)
        self.profile_name_entry.grid(row=2, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="Chunk").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.chunk_size_rows_entry = ttk.Entry(self.config_card, textvariable=self.chunk_size_rows_var, width=10)
        self.chunk_size_rows_entry.grid(row=3, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Workers").grid(row=3, column=2, sticky="w", pady=(6, 0))
        self.worker_count_entry = ttk.Entry(self.config_card, textvariable=self.worker_count_var, width=10)
        self.worker_count_entry.grid(row=3, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Inflight").grid(row=3, column=4, sticky="w", pady=(6, 0))
        self.max_inflight_chunks_entry = ttk.Entry(self.config_card, textvariable=self.max_inflight_chunks_var, width=10)
        self.max_inflight_chunks_entry.grid(row=3, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="Preview target").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.preview_row_target_entry = ttk.Entry(self.config_card, textvariable=self.preview_row_target_var, width=10)
        self.preview_row_target_entry.grid(row=4, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Page size").grid(row=4, column=2, sticky="w", pady=(6, 0))
        self.preview_page_size_entry = ttk.Entry(self.config_card, textvariable=self.preview_page_size_var, width=10)
        self.preview_page_size_entry.grid(row=4, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="SQLite batch").grid(row=4, column=4, sticky="w", pady=(6, 0))
        self.sqlite_batch_size_entry = ttk.Entry(self.config_card, textvariable=self.sqlite_batch_size_var, width=10)
        self.sqlite_batch_size_entry.grid(row=4, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="CSV buffer").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.csv_buffer_rows_entry = ttk.Entry(self.config_card, textvariable=self.csv_buffer_rows_var, width=10)
        self.csv_buffer_rows_entry.grid(row=5, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="FK cache").grid(row=5, column=2, sticky="w", pady=(6, 0))
        self.fk_cache_mode_combo = ttk.Combobox(
            self.config_card,
            textvariable=self.fk_cache_mode_var,
            state="readonly",
            values=FK_CACHE_MODES,
            width=12,
        )
        self.fk_cache_mode_combo.grid(row=5, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Retry").grid(row=5, column=4, sticky="w", pady=(6, 0))
        self.retry_limit_entry = ttk.Entry(self.config_card, textvariable=self.retry_limit_var, width=10)
        self.retry_limit_entry.grid(row=5, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="IPC queue").grid(row=6, column=0, sticky="w", pady=(6, 0))
        self.ipc_queue_size_entry = ttk.Entry(self.config_card, textvariable=self.ipc_queue_size_var, width=10)
        self.ipc_queue_size_entry.grid(row=6, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        self.strict_chunking_check = ttk.Checkbutton(
            self.config_card,
            text="Strict deterministic chunking",
            variable=self.strict_chunking_var,
        )
        self.strict_chunking_check.grid(row=6, column=2, columnspan=3, sticky="w", pady=(6, 0))

        actions = ttk.Frame(self.config_card)
        actions.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(10, 0))
        for idx in range(9):
            actions.columnconfigure(idx, weight=1)

        self.estimate_btn = None
        self.build_plan_btn = None
        self.run_benchmark_btn = None
        self.run_generate_btn = None
        self.start_run_btn = None
        self.start_fallback_btn = None

        col = 0
        if self.capabilities.estimate:
            self.estimate_btn = ttk.Button(actions, text="Estimate")
            self.estimate_btn.grid(row=0, column=col, sticky="ew", padx=(0, 4))
            col += 1
        if self.capabilities.build_plan:
            self.build_plan_btn = ttk.Button(actions, text="Build plan")
            self.build_plan_btn.grid(row=0, column=col, sticky="ew", padx=4)
            col += 1
        if self.capabilities.benchmark:
            self.run_benchmark_btn = ttk.Button(actions, text="Benchmark")
            self.run_benchmark_btn.grid(row=0, column=col, sticky="ew", padx=4)
            col += 1
        if self.capabilities.generate_strategy:
            self.run_generate_btn = ttk.Button(actions, text="Generate with strategy")
            self.run_generate_btn.grid(row=0, column=col, sticky="ew", padx=4)
            col += 1
        if self.capabilities.start_run:
            self.start_run_btn = ttk.Button(actions, text="Start")
            self.start_run_btn.grid(row=0, column=col, sticky="ew", padx=4)
            col += 1
        if self.capabilities.start_fallback:
            self.start_fallback_btn = ttk.Button(actions, text="Start + Fallback")
            self.start_fallback_btn.grid(row=0, column=col, sticky="ew", padx=4)
            col += 1

        self.cancel_run_btn = ttk.Button(actions, text="Cancel", state=tk.DISABLED)
        self.cancel_run_btn.grid(row=0, column=col, sticky="ew", padx=4)
        col += 1

        self.save_btn = ttk.Button(actions, text="Save config")
        self.save_btn.grid(row=0, column=col, sticky="ew", padx=4)
        col += 1
        self.load_btn = ttk.Button(actions, text="Load config")
        self.load_btn.grid(row=0, column=col, sticky="ew", padx=(4, 0))

        self.next_action_label = ttk.Label(
            self.config_card,
            textvariable=self.next_action_var,
            justify="left",
            wraplength=920,
        )
        self.next_action_label.grid(row=8, column=0, columnspan=6, sticky="ew", pady=(8, 0))

    def _build_progress_strip(self) -> None:
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100.0, value=0.0)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.live_progress = self.progress

        live = ttk.Frame(self)
        live.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(live, textvariable=self.live_phase_var).pack(side="left", padx=(0, 12))
        ttk.Label(live, textvariable=self.live_rows_var).pack(side="left", padx=(0, 12))
        ttk.Label(live, textvariable=self.live_eta_var).pack(side="left")

    def _build_results_workspace(self) -> None:
        self.results_tabs = ttk.Notebook(self)
        self.results_tabs.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.rowconfigure(3, weight=1)

        self._tab_by_key: dict[str, ttk.Frame] = {}

        if self.capabilities.estimate or self.capabilities.benchmark:
            self._tab_by_key["diagnostics"] = ttk.Frame(self.results_tabs, padding=8)
            self.results_tabs.add(self._tab_by_key["diagnostics"], text="Diagnostics")
        if self.capabilities.build_plan or self.capabilities.benchmark or self.capabilities.start_run or self.capabilities.generate_strategy:
            self._tab_by_key["plan"] = ttk.Frame(self.results_tabs, padding=8)
            self.results_tabs.add(self._tab_by_key["plan"], text="Plan")
        if self.capabilities.workers_tab:
            self._tab_by_key["workers"] = ttk.Frame(self.results_tabs, padding=8)
            self.results_tabs.add(self._tab_by_key["workers"], text="Workers")
        if self.capabilities.failures_tab:
            self._tab_by_key["failures"] = ttk.Frame(self.results_tabs, padding=8)
            self.results_tabs.add(self._tab_by_key["failures"], text="Failures")
        if self.capabilities.history_tab:
            self._tab_by_key["history"] = ttk.Frame(self.results_tabs, padding=8)
            self.results_tabs.add(self._tab_by_key["history"], text="History")

        for tab in self._tab_by_key.values():
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

        self.diagnostics_table = None
        self.plan_table = None
        self.worker_table = None
        self.failures_table = None
        self.history_table = None
        self._adapter_by_tree: dict[ttk.Treeview, VirtualTableAdapter] = {}
        self._tab_key_by_tree: dict[ttk.Treeview, str] = {}

        if "diagnostics" in self._tab_by_key:
            self.diagnostics_table = VirtualTableAdapter(
                self._tab_by_key["diagnostics"],
                columns=[
                    TableColumnSpec("table", "Table", 140),
                    TableColumnSpec("rows", "Rows", 90),
                    TableColumnSpec("memory", "Memory", 90),
                    TableColumnSpec("write", "Write", 90),
                    TableColumnSpec("time", "Time", 80),
                    TableColumnSpec("risk", "Risk", 70),
                    TableColumnSpec("recommendation", "Recommendation", 360, stretch=True),
                ],
                height=8,
                large_data_enabled=True,
                large_data_threshold_rows=1000,
                large_data_chunk_size=200,
                large_data_auto_pagination=True,
                large_data_auto_page_size=200,
            )
            self._adapter_by_tree[self.diagnostics_table.tree] = self.diagnostics_table
            self._tab_key_by_tree[self.diagnostics_table.tree] = "diagnostics"
            self._register_empty_hint("diagnostics")
            self._tab_row_counts["diagnostics"] = 0

        if "plan" in self._tab_by_key:
            self.plan_table = VirtualTableAdapter(
                self._tab_by_key["plan"],
                columns=[
                    TableColumnSpec("table", "Table", 140),
                    TableColumnSpec("partition", "Partition", 280, stretch=True),
                    TableColumnSpec("row_range", "Row range", 150),
                    TableColumnSpec("stage", "Stage", 80),
                    TableColumnSpec("worker", "Worker", 90),
                    TableColumnSpec("status", "Status", 100),
                ],
                height=8,
                large_data_enabled=True,
                large_data_threshold_rows=1000,
                large_data_chunk_size=200,
                large_data_auto_pagination=True,
                large_data_auto_page_size=200,
            )
            self._adapter_by_tree[self.plan_table.tree] = self.plan_table
            self._tab_key_by_tree[self.plan_table.tree] = "plan"
            self._register_empty_hint("plan")
            self._tab_row_counts["plan"] = 0

        if "workers" in self._tab_by_key:
            self.worker_table = VirtualTableAdapter(
                self._tab_by_key["workers"],
                columns=[
                    TableColumnSpec("worker", "Worker", 80),
                    TableColumnSpec("current", "Current table/partition", 280, stretch=True),
                    TableColumnSpec("rows", "Rows", 120),
                    TableColumnSpec("throughput", "Rows/s", 120),
                    TableColumnSpec("memory", "Memory MB", 120),
                    TableColumnSpec("heartbeat", "Last heartbeat", 130),
                    TableColumnSpec("state", "State", 100),
                ],
                height=8,
                large_data_enabled=True,
                large_data_threshold_rows=1000,
                large_data_chunk_size=200,
                large_data_auto_pagination=True,
                large_data_auto_page_size=200,
            )
            self._adapter_by_tree[self.worker_table.tree] = self.worker_table
            self._tab_key_by_tree[self.worker_table.tree] = "workers"
            self._register_empty_hint("workers")
            self._tab_row_counts["workers"] = 0

        if "failures" in self._tab_by_key:
            self.failures_table = VirtualTableAdapter(
                self._tab_by_key["failures"],
                columns=[
                    TableColumnSpec("partition", "Partition", 240),
                    TableColumnSpec("error", "Error", 460, stretch=True),
                    TableColumnSpec("retry", "Retry", 80),
                    TableColumnSpec("action", "Action", 120),
                ],
                height=8,
                large_data_enabled=True,
                large_data_threshold_rows=1000,
                large_data_chunk_size=200,
            )
            self._adapter_by_tree[self.failures_table.tree] = self.failures_table
            self._tab_key_by_tree[self.failures_table.tree] = "failures"
            self._register_empty_hint("failures")
            self._tab_row_counts["failures"] = 0

        if "history" in self._tab_by_key:
            self.history_table = VirtualTableAdapter(
                self._tab_by_key["history"],
                columns=[
                    TableColumnSpec("timestamp", "Timestamp", 170),
                    TableColumnSpec("status", "Status", 170),
                    TableColumnSpec("mode", "Mode", 150),
                    TableColumnSpec("fallback", "Fallback", 90),
                    TableColumnSpec("rows", "Rows", 110),
                ],
                height=8,
                large_data_enabled=True,
                large_data_threshold_rows=1000,
                large_data_chunk_size=200,
            )
            self._adapter_by_tree[self.history_table.tree] = self.history_table
            self._tab_key_by_tree[self.history_table.tree] = "history"
            self._register_empty_hint("history")
            self._tab_row_counts["history"] = 0

        self.diagnostics_tree = self.diagnostics_table.tree if self.diagnostics_table else None
        self.preview_table = self.plan_table.tree if self.plan_table else None
        self.chunk_plan_tree = self.preview_table
        self.partition_tree = self.preview_table
        self.worker_tree = self.worker_table.tree if self.worker_table else None
        self.failures_tree = self.failures_table.tree if self.failures_table else None
        self.history_tree = self.history_table.tree if self.history_table else None
        self._refresh_guidance_hints()

    def _build_status_region(self) -> None:
        self.inline_error_label = ttk.Label(self, textvariable=self.inline_error_var, foreground="#9b1c1c")
        self.inline_error_label.grid(row=4, column=0, sticky="w", pady=(0, 4))

        if self.capabilities.show_status_label:
            self.status_label = ttk.Label(self, textvariable=self.status_var)
            self.status_label.grid(row=5, column=0, sticky="w")

    def _register_empty_hint(self, key: str) -> None:
        tab = self._tab_by_key.get(key)
        if tab is None:
            return
        label = ttk.Label(tab, justify="center", anchor="center", wraplength=760)
        label.place(relx=0.5, rely=0.5, anchor="center")
        self._empty_hint_label_by_key[key] = label

    @staticmethod
    def _empty_hint_message(key: str, *, schema_ready: bool) -> str:
        if key == "diagnostics":
            if schema_ready:
                return "No diagnostics yet. Next action: run Estimate or Benchmark."
            return "No diagnostics yet. Next action: load a schema first."
        if key == "plan":
            if schema_ready:
                return "No plan yet. Next action: run Build plan, Benchmark, or Start."
            return "No plan yet. Next action: load a schema first."
        if key == "workers":
            if schema_ready:
                return "No worker activity yet. Next action: start a run."
            return "No worker activity yet. Next action: load a schema first."
        if key == "failures":
            if schema_ready:
                return "No failures logged. Failures appear here only when partitions fail."
            return "No failures yet. Next action: load a schema first."
        if key == "history":
            if schema_ready:
                return "No run history yet. Completed benchmarks/runs will appear here."
            return "No run history yet. Next action: load a schema first."
        return "No rows yet."

    def _set_tab_row_count(self, key: str, count: int) -> None:
        self._tab_row_counts[key] = max(0, int(count))
        self._refresh_guidance_hints()

    def _refresh_guidance_hints(self) -> None:
        schema_ready = self.schema_path_var.get().strip() != ""
        populated_tabs = [key for key, count in self._tab_row_counts.items() if count > 0]
        total_rows = sum(self._tab_row_counts.values())

        if not schema_ready:
            self.next_action_var.set(
                "Next action: browse or paste a schema JSON path, then click Load."
            )
        elif total_rows == 0:
            self.next_action_var.set(
                "Schema path is set. Next action: click Load, then run Estimate/Build plan/Start."
            )
        else:
            summary = ", ".join(
                f"{key}={self._tab_row_counts[key]}"
                for key in ("diagnostics", "plan", "workers", "failures", "history")
                if self._tab_row_counts.get(key, 0) > 0
            )
            self.next_action_var.set(
                f"Results ready ({summary}). Next action: review tabs or continue with another run action."
            )

        for key, label in self._empty_hint_label_by_key.items():
            row_count = self._tab_row_counts.get(key, 0)
            if row_count > 0:
                label.place_forget()
                continue
            label.configure(text=self._empty_hint_message(key, schema_ready=schema_ready))
            if not label.winfo_ismapped():
                label.place(relx=0.5, rely=0.5, anchor="center")

        for key in populated_tabs:
            label = self._empty_hint_label_by_key.get(key)
            if label is not None:
                label.place_forget()

    def _on_schema_path_changed(self, *_args) -> None:
        self._refresh_guidance_hints()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        if self._status_callback is not None:
            self._status_callback(text)

    def set_inline_error(self, text: str) -> None:
        self.inline_error_var.set(text)

    def set_focus(self, key: str) -> None:
        tab = self._tab_by_key.get(key)
        if tab is not None:
            self.results_tabs.select(tab)

    def sync_model_from_vars(self) -> RunWorkflowViewModel:
        self.model.schema_path = self.schema_path_var.get().strip()
        self.model.target_tables = self.target_tables_var.get().strip()
        self.model.row_overrides_json = self.row_overrides_var.get().strip()
        self.model.preview_row_target = self.preview_row_target_var.get().strip()
        self.model.output_mode = coerce_output_mode(self.output_mode_var.get())
        self.model.chunk_size_rows = self.chunk_size_rows_var.get().strip()
        self.model.preview_page_size = self.preview_page_size_var.get().strip()
        self.model.sqlite_batch_size = self.sqlite_batch_size_var.get().strip()
        self.model.csv_buffer_rows = self.csv_buffer_rows_var.get().strip()
        self.model.fk_cache_mode = self.fk_cache_mode_var.get().strip()
        self.model.strict_deterministic_chunking = bool(self.strict_chunking_var.get())
        self.model.execution_mode = coerce_execution_mode(self.execution_mode_var.get())
        self.model.worker_count = self.worker_count_var.get().strip()
        self.model.max_inflight_chunks = self.max_inflight_chunks_var.get().strip()
        self.model.ipc_queue_size = self.ipc_queue_size_var.get().strip()
        self.model.retry_limit = self.retry_limit_var.get().strip()
        self.model.profile_name = self.profile_name_var.get().strip() or "default_v2_profile"
        return self.model

    def sync_vars_from_model(self) -> None:
        self.schema_path_var.set(self.model.schema_path)
        self.target_tables_var.set(self.model.target_tables)
        self.row_overrides_var.set(self.model.row_overrides_json)
        self.preview_row_target_var.set(self.model.preview_row_target)
        self.output_mode_var.set(coerce_output_mode(self.model.output_mode))
        self.chunk_size_rows_var.set(self.model.chunk_size_rows)
        self.preview_page_size_var.set(self.model.preview_page_size)
        self.sqlite_batch_size_var.set(self.model.sqlite_batch_size)
        self.csv_buffer_rows_var.set(self.model.csv_buffer_rows)
        self.fk_cache_mode_var.set(self.model.fk_cache_mode)
        self.strict_chunking_var.set(bool(self.model.strict_deterministic_chunking))
        self.execution_mode_var.set(coerce_execution_mode(self.model.execution_mode))
        self.worker_count_var.set(self.model.worker_count)
        self.max_inflight_chunks_var.set(self.model.max_inflight_chunks)
        self.ipc_queue_size_var.set(self.model.ipc_queue_size)
        self.retry_limit_var.set(self.model.retry_limit)
        self.profile_name_var.set(self.model.profile_name)
        self._refresh_guidance_hints()

    def clear_tree(self, tree: ttk.Treeview | None) -> None:
        if tree is None:
            return
        adapter = self._adapter_by_tree.get(tree)
        if adapter is not None:
            adapter.clear()
            key = self._tab_key_by_tree.get(tree)
            if key is not None:
                self._set_tab_row_count(key, 0)
            return
        for item in tree.get_children():
            tree.delete(item)

    def set_diagnostics_rows(self, rows: list[tuple[object, ...]] | list[list[object]]) -> None:
        if self.diagnostics_table is not None:
            self.diagnostics_table.set_rows(rows)
            self._set_tab_row_count("diagnostics", len(rows))

    def set_plan_rows(self, rows: list[tuple[object, ...]] | list[list[object]]) -> None:
        if self.plan_table is not None:
            self.plan_table.set_rows(rows)
            self._set_tab_row_count("plan", len(rows))

    def set_worker_rows(self, rows: list[tuple[object, ...]] | list[list[object]]) -> None:
        if self.worker_table is not None:
            self.worker_table.set_rows(rows)
            self._set_tab_row_count("workers", len(rows))

    def set_failures_rows(self, rows: list[tuple[object, ...]] | list[list[object]]) -> None:
        if self.failures_table is not None:
            self.failures_table.set_rows(rows)
            self._set_tab_row_count("failures", len(rows))

    def set_history_rows(self, rows: list[tuple[object, ...]] | list[list[object]]) -> None:
        if self.history_table is not None:
            self.history_table.set_rows(rows)
            self._set_tab_row_count("history", len(rows))

    @property
    def run_action_buttons(self) -> list[object]:
        buttons: list[object] = []
        for btn in (
            self.estimate_btn,
            self.build_plan_btn,
            self.run_benchmark_btn,
            self.run_generate_btn,
            self.start_run_btn,
            self.start_fallback_btn,
        ):
            if btn is not None:
                buttons.append(btn)
        return buttons
