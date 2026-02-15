
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.config import AppConfig
from src.multiprocessing_runtime import EXECUTION_MODES
from src.multiprocessing_runtime import MultiprocessConfig
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunCancelled
from src.multiprocessing_runtime import MultiprocessRunResult
from src.multiprocessing_runtime import PartitionFailure
from src.multiprocessing_runtime import PartitionPlanEntry
from src.multiprocessing_runtime import WorkerStatus
from src.multiprocessing_runtime import build_multiprocess_config
from src.multiprocessing_runtime import build_partition_plan
from src.multiprocessing_runtime import build_worker_status_snapshot
from src.multiprocessing_runtime import multiprocess_config_from_payload
from src.multiprocessing_runtime import multiprocess_config_to_payload
from src.multiprocessing_runtime import run_generation_with_multiprocessing
from src.performance_scaling import FK_CACHE_MODES
from src.performance_scaling import OUTPUT_MODES
from src.performance_scaling import build_performance_profile
from src.schema_project_io import load_project_from_json


class ExecutionOrchestratorScreen(ttk.Frame):
    """Multiprocessing run planner/monitor with retry and fallback controls."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._loaded_schema_path = ""

        cpu_count = max(1, int(os.cpu_count() or 1))
        default_workers = max(1, min(4, cpu_count))

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

        self.mode_var = tk.StringVar(value=EXECUTION_MODES[1])
        self.worker_count_var = tk.StringVar(value=str(default_workers))
        self.max_inflight_chunks_var = tk.StringVar(value=str(default_workers * 2))
        self.ipc_queue_size_var = tk.StringVar(value="128")
        self.retry_limit_var = tk.StringVar(value="1")

        self.status_var = tk.StringVar(value="Load a schema and build a partition plan.")
        self.live_phase_var = tk.StringVar(value="Idle")
        self.live_rows_var = tk.StringVar(value="Rows processed: 0")
        self.live_eta_var = tk.StringVar(value="ETA: --")

        self._is_running = False
        self._cancel_requested = False
        self._run_started_at = 0.0

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=lambda: self.app.go_home()).pack(side="left")
        ttk.Label(header, text="Execution Orchestrator", font=("Segoe UI", 16, "bold")).pack(
            side="left",
            padx=(10, 0),
        )
        ttk.Button(header, text="Load run config...", command=self._load_run_config).pack(side="right")
        ttk.Button(header, text="Save run config...", command=self._save_run_config).pack(side="right", padx=(0, 8))

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=940,
            text=(
                "Configure execution mode and worker controls, build FK-staged partitions, "
                "run with retries, and fallback to single-process when needed."
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
        for idx in (1, 3):
            profile_panel.columnconfigure(idx, weight=1)

        ttk.Label(profile_panel, text="Target tables (comma-separated)").grid(row=0, column=0, sticky="w")
        ttk.Entry(profile_panel, textvariable=self.target_tables_var).grid(row=0, column=1, sticky="ew", padx=(8, 20))

        ttk.Label(profile_panel, text="Row overrides JSON").grid(row=0, column=2, sticky="w")
        ttk.Entry(profile_panel, textvariable=self.row_overrides_var).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(profile_panel, text="Output mode").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            profile_panel,
            textvariable=self.output_mode_var,
            state="readonly",
            values=OUTPUT_MODES,
            width=20,
        ).grid(row=1, column=1, sticky="w", padx=(8, 20), pady=(6, 0))

        ttk.Label(profile_panel, text="Chunk size rows").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.chunk_size_rows_var).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(6, 0))

        ttk.Label(profile_panel, text="Preview row target").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.preview_row_target_var).grid(
            row=2,
            column=1,
            sticky="w",
            padx=(8, 20),
            pady=(6, 0),
        )

        ttk.Label(profile_panel, text="Preview page size").grid(row=2, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.preview_page_size_var).grid(
            row=2,
            column=3,
            sticky="w",
            padx=(8, 0),
            pady=(6, 0),
        )

        ttk.Label(profile_panel, text="SQLite batch size").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.sqlite_batch_size_var).grid(
            row=3,
            column=1,
            sticky="w",
            padx=(8, 20),
            pady=(6, 0),
        )

        ttk.Label(profile_panel, text="CSV buffer rows").grid(row=3, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(profile_panel, textvariable=self.csv_buffer_rows_var).grid(
            row=3,
            column=3,
            sticky="w",
            padx=(8, 0),
            pady=(6, 0),
        )

        ttk.Label(profile_panel, text="FK cache mode").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            profile_panel,
            textvariable=self.fk_cache_mode_var,
            state="readonly",
            values=FK_CACHE_MODES,
            width=20,
        ).grid(row=4, column=1, sticky="w", padx=(8, 20), pady=(6, 0))

        ttk.Checkbutton(
            profile_panel,
            text="Strict deterministic chunking",
            variable=self.strict_chunking_var,
        ).grid(row=4, column=2, sticky="w", pady=(6, 0))

        execution_panel = ttk.LabelFrame(self, text="Execution mode", padding=8)
        execution_panel.pack(fill="x", pady=(0, 8))
        for idx in (1, 3, 5):
            execution_panel.columnconfigure(idx, weight=1)

        ttk.Label(execution_panel, text="Mode").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            execution_panel,
            textvariable=self.mode_var,
            state="readonly",
            values=EXECUTION_MODES,
            width=24,
        ).grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Label(execution_panel, text="Worker count").grid(row=0, column=2, sticky="w")
        ttk.Entry(execution_panel, textvariable=self.worker_count_var, width=12).grid(
            row=0,
            column=3,
            sticky="w",
            padx=(8, 20),
        )

        ttk.Label(execution_panel, text="Max inflight chunks").grid(row=0, column=4, sticky="w")
        ttk.Entry(execution_panel, textvariable=self.max_inflight_chunks_var, width=12).grid(
            row=0,
            column=5,
            sticky="w",
            padx=(8, 0),
        )

        ttk.Label(execution_panel, text="IPC queue size").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(execution_panel, textvariable=self.ipc_queue_size_var, width=12).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(8, 20),
            pady=(6, 0),
        )

        ttk.Label(execution_panel, text="Retry limit").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(execution_panel, textvariable=self.retry_limit_var, width=12).grid(
            row=1,
            column=3,
            sticky="w",
            padx=(8, 20),
            pady=(6, 0),
        )

        controls = ttk.LabelFrame(self, text="Run controls", padding=8)
        controls.pack(fill="x", pady=(0, 8))
        for idx in range(4):
            controls.columnconfigure(idx, weight=1)

        self.build_plan_btn = ttk.Button(controls, text="Build plan", command=self._build_plan)
        self.build_plan_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.start_run_btn = ttk.Button(controls, text="Start", command=self._start_run)
        self.start_run_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.start_fallback_btn = ttk.Button(
            controls,
            text="Start with fallback",
            command=lambda: self._start_run(fallback_to_single_process=True),
        )
        self.start_fallback_btn.grid(row=0, column=2, sticky="ew", padx=4)

        self.cancel_run_btn = ttk.Button(
            controls,
            text="Cancel",
            command=self._cancel_run,
            state=tk.DISABLED,
        )
        self.cancel_run_btn.grid(row=0, column=3, sticky="ew", padx=(4, 0))

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

        plan_box = ttk.Frame(results, padding=8)
        worker_box = ttk.Frame(results, padding=8)
        failure_box = ttk.Frame(results, padding=8)
        results.add(plan_box, text="Partition plan")
        results.add(worker_box, text="Workers")
        results.add(failure_box, text="Failures")

        for box in (plan_box, worker_box, failure_box):
            box.columnconfigure(0, weight=1)
            box.rowconfigure(0, weight=1)

        plan_columns = ("table", "partition", "row_range", "stage", "worker", "status")
        self.partition_tree = ttk.Treeview(plan_box, columns=plan_columns, show="headings", height=10)
        self.partition_tree.grid(row=0, column=0, sticky="nsew")

        for column, heading, width in (
            ("table", "Table", 180),
            ("partition", "Partition", 250),
            ("row_range", "Row range", 180),
            ("stage", "Stage", 90),
            ("worker", "Worker", 100),
            ("status", "Status", 120),
        ):
            self.partition_tree.heading(column, text=heading, anchor="w")
            self.partition_tree.column(column, width=width, anchor="w")

        worker_columns = ("worker", "current", "rows", "throughput", "memory", "heartbeat", "state")
        self.worker_tree = ttk.Treeview(worker_box, columns=worker_columns, show="headings", height=10)
        self.worker_tree.grid(row=0, column=0, sticky="nsew")

        for column, heading, width in (
            ("worker", "Worker", 80),
            ("current", "Current table/partition", 280),
            ("rows", "Rows", 120),
            ("throughput", "Rows/s", 110),
            ("memory", "Memory MB", 110),
            ("heartbeat", "Last heartbeat", 140),
            ("state", "State", 120),
        ):
            self.worker_tree.heading(column, text=heading, anchor="w")
            self.worker_tree.column(column, width=width, anchor="w")

        failure_columns = ("partition", "error", "retry", "action")
        self.failures_tree = ttk.Treeview(failure_box, columns=failure_columns, show="headings", height=10)
        self.failures_tree.grid(row=0, column=0, sticky="nsew")

        for column, heading, width in (
            ("partition", "Partition", 250),
            ("error", "Error", 460),
            ("retry", "Retry count", 120),
            ("action", "Action", 100),
        ):
            self.failures_tree.heading(column, text=heading, anchor="w")
            self.failures_tree.column(column, width=width, anchor="w")

        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

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
                "Execution orchestrator error",
                (
                    "Execution Orchestrator / Schema path: path is required. "
                    "Fix: browse to an existing schema project JSON file."
                ),
            )
            return False
        try:
            loaded = load_project_from_json(schema_path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Execution orchestrator error", str(exc))
            return False
        self.project = loaded
        self._loaded_schema_path = schema_path
        self._clear_partition_tree()
        self._clear_worker_tree()
        self._clear_failures_tree()
        self.status_var.set(f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables.")
        return True

    def _ensure_project(self) -> bool:
        path_now = self.schema_path_var.get().strip()
        if self.project is None:
            return self._load_schema()
        if path_now == "":
            return True
        if path_now != self._loaded_schema_path:
            return self._load_schema()
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

    def _build_config(self) -> MultiprocessConfig:
        return build_multiprocess_config(
            mode_value=self.mode_var.get(),
            worker_count_value=self.worker_count_var.get(),
            max_inflight_chunks_value=self.max_inflight_chunks_var.get(),
            ipc_queue_size_value=self.ipc_queue_size_var.get(),
            retry_limit_value=self.retry_limit_var.get(),
        )

    def _build_plan(self) -> None:
        if self._is_running:
            return
        if not self._ensure_project():
            return
        assert self.project is not None
        try:
            profile = self._build_profile()
            config = self._build_config()
            plan = build_partition_plan(self.project, profile, config)
            workers = build_worker_status_snapshot(config)
        except ValueError as exc:
            messagebox.showerror("Execution orchestrator error", str(exc))
            return

        self._populate_partition_tree(plan)
        self._populate_worker_tree(workers)
        total_rows = sum(entry.rows_in_partition for entry in plan)
        self.status_var.set(
            (
                "Partition plan ready: "
                f"partitions={len(plan)}, rows={total_rows}, workers={len(workers)}."
            )
        )

    def _populate_partition_tree(self, entries: list[PartitionPlanEntry]) -> None:
        self._clear_partition_tree()
        for entry in entries:
            self.partition_tree.insert(
                "",
                "end",
                values=(
                    entry.table_name,
                    entry.partition_id,
                    f"{entry.start_row}-{entry.end_row}",
                    str(entry.stage),
                    str(entry.assigned_worker),
                    entry.status,
                ),
            )

    def _populate_worker_tree(self, workers: dict[int, WorkerStatus]) -> None:
        self._clear_worker_tree()
        for worker_id in sorted(workers):
            worker = workers[worker_id]
            heartbeat = "--"
            if worker.last_heartbeat_epoch > 0:
                heartbeat = time.strftime("%H:%M:%S", time.localtime(worker.last_heartbeat_epoch))
            current = ""
            if worker.current_partition_id:
                current = f"{worker.current_table} / {worker.current_partition_id}"
            self.worker_tree.insert(
                "",
                "end",
                values=(
                    str(worker.worker_id),
                    current,
                    str(worker.rows_processed),
                    f"{worker.throughput_rows_per_sec:.1f}",
                    f"{worker.memory_mb:.3f}",
                    heartbeat,
                    worker.state,
                ),
            )

    def _append_failure(self, failure: PartitionFailure) -> None:
        self.failures_tree.insert(
            "",
            "end",
            values=(
                failure.partition_id,
                failure.error,
                str(failure.retry_count),
                failure.action,
            ),
        )

    def _clear_partition_tree(self) -> None:
        for item in self.partition_tree.get_children():
            self.partition_tree.delete(item)

    def _clear_worker_tree(self) -> None:
        for item in self.worker_tree.get_children():
            self.worker_tree.delete(item)

    def _clear_failures_tree(self) -> None:
        for item in self.failures_tree.get_children():
            self.failures_tree.delete(item)

    def _set_running(self, running: bool, phase: str) -> None:
        self._is_running = running
        self.live_phase_var.set(phase)
        if running:
            self._run_started_at = time.monotonic()
            self._cancel_requested = False
            self.cancel_run_btn.configure(state=tk.NORMAL)
            self.build_plan_btn.configure(state=tk.DISABLED)
            self.start_run_btn.configure(state=tk.DISABLED)
            self.start_fallback_btn.configure(state=tk.DISABLED)
        else:
            self.cancel_run_btn.configure(state=tk.DISABLED)
            self.build_plan_btn.configure(state=tk.NORMAL)
            self.start_run_btn.configure(state=tk.NORMAL)
            self.start_fallback_btn.configure(state=tk.NORMAL)

    def _cancel_run(self) -> None:
        if not self._is_running:
            return
        self._cancel_requested = True
        self.live_phase_var.set("Cancelling...")
        self.status_var.set("Cancellation requested. Waiting for current task to stop...")

    def _is_cancel_requested(self) -> bool:
        return self._cancel_requested

    def _on_runtime_event(self, event: MultiprocessEvent) -> None:
        if event.kind == "started":
            self.live_progress.configure(value=0.0)
            self.live_phase_var.set(event.message or "Run started.")
            self.live_rows_var.set(f"Rows processed: 0/{event.total_rows}")
            self.live_eta_var.set("ETA: calculating...")
            return

        if event.kind == "progress":
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

        if event.kind == "partition_failed":
            self.live_phase_var.set(event.message or "Partition failed.")
            if event.partition_id:
                self.failures_tree.insert(
                    "",
                    "end",
                    values=(
                        event.partition_id,
                        event.message,
                        str(event.retry_count),
                        "retry",
                    ),
                )
            return

        if event.kind == "fallback":
            self.live_phase_var.set(event.message or "Fallback to single-process.")
            self.live_eta_var.set("ETA: fallback")
            return

        if event.kind == "run_done":
            self.live_progress.configure(value=100.0)
            self.live_phase_var.set(event.message or "Run complete.")
            self.live_rows_var.set(f"Rows processed: {event.rows_processed}/{event.total_rows}")
            elapsed = max(0.001, time.monotonic() - self._run_started_at)
            rate = float(event.rows_processed) / elapsed if event.rows_processed > 0 else 0.0
            self.live_eta_var.set(f"Completed in {elapsed:.2f}s @ {rate:.1f} rows/s")
            return

    def _run_worker(self, target, *, phase_label: str) -> None:
        if self._is_running:
            return
        self._set_running(True, phase_label)

        def work() -> None:
            try:
                target()
            except MultiprocessRunCancelled as exc:
                self.after(0, lambda: self._on_run_cancelled(str(exc)))
            except ValueError as exc:
                self.after(0, lambda: self._on_run_failed(str(exc)))
            except Exception as exc:
                self.after(0, lambda: self._on_run_failed(str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _on_run_failed(self, message: str) -> None:
        self._set_running(False, "Failed")
        self.status_var.set(message)
        messagebox.showerror("Execution orchestrator error", message)

    def _on_run_cancelled(self, message: str) -> None:
        self._set_running(False, "Cancelled")
        self.live_phase_var.set("Run cancelled.")
        self.live_eta_var.set("ETA: cancelled")
        self.status_var.set(message)

    def _on_run_done(self, result: MultiprocessRunResult) -> None:
        self._set_running(False, "Complete")
        self._populate_partition_tree(result.partition_plan)
        self._populate_worker_tree(result.worker_status)
        self._clear_failures_tree()
        for failure in result.failures:
            self._append_failure(failure)

        csv_count = len(result.strategy_result.csv_paths)
        sqlite_rows = sum(result.strategy_result.sqlite_counts.values())
        fallback_text = "yes" if result.fallback_used else "no"
        self.status_var.set(
            (
                "Run complete: "
                f"rows={result.total_rows}, csv_files={csv_count}, sqlite_rows={sqlite_rows}, "
                f"fallback={fallback_text}."
            )
        )

    def _start_run(self, fallback_to_single_process: bool = False) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None

        try:
            profile = self._build_profile()
            config = self._build_config()
        except ValueError as exc:
            messagebox.showerror("Execution orchestrator error", str(exc))
            return

        output_mode = profile.output_mode
        output_csv_folder: str | None = None
        output_sqlite_path: str | None = None

        if output_mode in {"csv", "all"}:
            output_csv_folder = filedialog.askdirectory(
                title="Choose output folder for CSV export",
            )
            if output_csv_folder in {None, ""}:
                self.status_var.set("Run cancelled (no CSV output folder selected).")
                return

        if output_mode in {"sqlite", "all"}:
            output_sqlite_path = filedialog.asksaveasfilename(
                title="Choose SQLite output path",
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
                initialfile="execution_orchestrator.db",
            )
            if output_sqlite_path in {None, ""}:
                self.status_var.set("Run cancelled (no SQLite output path selected).")
                return

        def target() -> None:
            result = run_generation_with_multiprocessing(
                self.project,
                profile,
                config,
                output_csv_folder=output_csv_folder,
                output_sqlite_path=output_sqlite_path,
                on_event=lambda e: self.after(0, lambda evt=e: self._on_runtime_event(evt)),
                cancel_requested=self._is_cancel_requested,
                fallback_to_single_process=fallback_to_single_process,
            )
            self.after(0, lambda: self._on_run_done(result))

        label = "Running with fallback..." if fallback_to_single_process else "Running..."
        self._run_worker(target, phase_label=label)

    def _save_run_config(self) -> None:
        try:
            profile = self._build_profile()
            config = self._build_config()
        except ValueError as exc:
            messagebox.showerror("Execution orchestrator error", str(exc))
            return

        output_path = filedialog.asksaveasfilename(
            title="Save execution run config JSON",
            defaultextension=".json",
            initialfile="execution_orchestrator_config.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.status_var.set("Save run config cancelled.")
            return

        payload = {
            "profile": {
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
            },
            "multiprocess": multiprocess_config_to_payload(config),
        }

        try:
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(
                "Execution orchestrator error",
                (
                    "Execution Orchestrator / Save run config: could not write config file "
                    f"({exc}). Fix: choose a writable output path."
                ),
            )
            return

        self.status_var.set(f"Saved run config to {output_path}.")

    def _load_run_config(self) -> None:
        config_path = filedialog.askopenfilename(
            title="Load execution run config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if config_path == "":
            self.status_var.set("Load run config cancelled.")
            return

        try:
            payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror(
                "Execution orchestrator error",
                (
                    "Execution Orchestrator / Load run config: failed to read config JSON "
                    f"({exc}). Fix: choose a valid JSON config file."
                ),
            )
            return

        if not isinstance(payload, dict):
            messagebox.showerror(
                "Execution orchestrator error",
                (
                    "Execution Orchestrator / Load run config: config JSON must be an object. "
                    "Fix: store profile and multiprocess fields in a JSON object."
                ),
            )
            return

        profile_payload = payload.get("profile", {})
        multiprocess_payload = payload.get("multiprocess", {})
        if not isinstance(profile_payload, dict) or not isinstance(multiprocess_payload, dict):
            messagebox.showerror(
                "Execution orchestrator error",
                (
                    "Execution Orchestrator / Load run config: invalid config structure. "
                    "Fix: include object fields 'profile' and 'multiprocess'."
                ),
            )
            return

        try:
            target_tables = profile_payload.get("target_tables", [])
            if isinstance(target_tables, list):
                self.target_tables_var.set(", ".join(str(item).strip() for item in target_tables if str(item).strip() != ""))
            else:
                self.target_tables_var.set("")

            row_overrides = profile_payload.get("row_overrides", {})
            if row_overrides in ({}, None):
                self.row_overrides_var.set("")
            else:
                self.row_overrides_var.set(json.dumps(row_overrides, separators=(",", ":")))

            self.preview_row_target_var.set(str(profile_payload.get("preview_row_target", 500)))
            self.output_mode_var.set(str(profile_payload.get("output_mode", OUTPUT_MODES[0])))
            self.chunk_size_rows_var.set(str(profile_payload.get("chunk_size_rows", 10000)))
            self.preview_page_size_var.set(str(profile_payload.get("preview_page_size", 500)))
            self.sqlite_batch_size_var.set(str(profile_payload.get("sqlite_batch_size", 5000)))
            self.csv_buffer_rows_var.set(str(profile_payload.get("csv_buffer_rows", 5000)))
            self.fk_cache_mode_var.set(str(profile_payload.get("fk_cache_mode", FK_CACHE_MODES[0])))
            self.strict_chunking_var.set(bool(profile_payload.get("strict_deterministic_chunking", True)))

            config = multiprocess_config_from_payload(multiprocess_payload)
            self.mode_var.set(config.mode)
            self.worker_count_var.set(str(config.worker_count))
            self.max_inflight_chunks_var.set(str(config.max_inflight_chunks))
            self.ipc_queue_size_var.set(str(config.ipc_queue_size))
            self.retry_limit_var.set(str(config.retry_limit))

            # Re-validate to fail fast with actionable messages.
            self._build_profile()
            self._build_config()
        except ValueError as exc:
            messagebox.showerror("Execution orchestrator error", str(exc))
            return

        self.status_var.set(f"Loaded run config from {config_path}.")
