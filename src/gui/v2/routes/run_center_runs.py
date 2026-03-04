from __future__ import annotations

import time
from tkinter import ttk

from src.gui.v2.routes import run_hooks
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunCancelled
from src.multiprocessing_runtime import MultiprocessRunResult
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import PerformanceRunCancelled
from src.performance_scaling import RuntimeEvent


def _clear_tree(self, tree: ttk.Treeview | None) -> None:
    self.surface.clear_tree(tree)


def _set_running(self, running: bool, phase: str) -> None:
    self.lifecycle.set_running(running, phase)


def _cancel_run(self) -> None:
    self.lifecycle.request_cancel("Cancellation requested. Waiting for current step to stop...")


def _is_cancel_requested(self) -> bool:
    return self.lifecycle.is_cancel_requested()


def _append_history(self, status: str, mode: str, fallback: bool, rows: int) -> None:
    if self.history_tree is None:
        return
    self.history_tree.insert(
        "",
        0,
        values=(time.strftime("%Y-%m-%d %H:%M:%S"), status, mode, "yes" if fallback else "no", str(rows)),
    )


def _on_runtime_event(self, event: RuntimeEvent) -> None:
    self.lifecycle.handle_runtime_event(event)


def _on_multiprocess_event(self, event: MultiprocessEvent) -> None:
    self.lifecycle.handle_multiprocess_event(event)
    if event.kind == "partition_failed" and event.partition_id and self.failures_tree is not None:
        self.failures_tree.insert(
            "",
            "end",
            values=(event.partition_id, event.message, str(event.retry_count), "retry"),
        )


def _on_run_failed(self, message: str) -> None:
    self.lifecycle.transition_failed(message, phase="Failed")
    self.error_surface.emit_formatted(message, mode="mixed")
    self._append_history("failed", self.surface.execution_mode_var.get(), False, 0)


def _on_run_cancelled(self, message: str) -> None:
    self.lifecycle.transition_cancelled(message, phase="Cancelled")
    self.live_phase_var.set("Run cancelled.")
    self.live_eta_var.set("ETA: cancelled")
    self._notify("Run cancelled by user request.", level="warn", duration_ms=3200)
    self._append_history("cancelled", self.surface.execution_mode_var.get(), False, 0)


def _run_estimate(self) -> None:
    if self.lifecycle.state.is_running or not self._ensure_project():
        return
    assert self.project is not None
    model = self._sync_viewmodel_from_vars()
    try:
        diagnostics = run_hooks.run_shared_estimate(self.project, model)
    except ValueError as exc:
        self.error_surface.emit_exception_actionable(
            exc,
            location="Estimate workload",
            hint="review run profile values and retry",
            mode="mixed",
        )
        return
    self.surface.set_diagnostics_rows(
        [
            (
                estimate.table_name,
                str(estimate.estimated_rows),
                f"{estimate.estimated_memory_mb:.3f}",
                f"{estimate.estimated_write_mb:.3f}",
                f"{estimate.estimated_seconds:.3f}",
                estimate.risk_level,
                estimate.recommendation,
            )
            for estimate in diagnostics.estimates
        ]
    )
    self._notify(
        f"Estimate complete: rows={diagnostics.summary.total_rows}, risk={diagnostics.summary.highest_risk}.",
        level="success",
        duration_ms=3400,
    )
    self._set_focus("diagnostics")


def _run_build_plan(self) -> None:
    if self.lifecycle.state.is_running or not self._ensure_project():
        return
    assert self.project is not None
    model = self._sync_viewmodel_from_vars()
    try:
        entries = run_hooks.run_shared_build_partition_plan(self.project, model)
    except ValueError as exc:
        self.error_surface.emit_exception_actionable(
            exc,
            location="Build partition plan",
            hint="review execution settings and retry",
            mode="mixed",
        )
        return
    self.surface.set_plan_rows(
        [
            (
                entry.table_name,
                entry.partition_id,
                f"{entry.start_row}-{entry.end_row}",
                str(entry.stage),
                str(entry.assigned_worker),
                entry.status,
            )
            for entry in entries
        ]
    )
    self._notify(
        f"Partition plan ready: partitions={len(entries)}.",
        level="success",
        duration_ms=3400,
    )
    self._set_focus("plan")


def _start_benchmark(self) -> None:
    if not self._ensure_project():
        return
    assert self.project is not None
    model = self._sync_viewmodel_from_vars()

    def worker() -> BenchmarkResult:
        return run_hooks.run_shared_benchmark(
            self.project,
            model,
            on_event=self.ui_dispatch.marshal(self._on_runtime_event),
            cancel_requested=self._is_cancel_requested,
        )

    def on_done(result: BenchmarkResult) -> None:
        self.lifecycle.transition_complete("Benchmark complete")
        self.surface.set_diagnostics_rows(
            [
                (
                    estimate.table_name,
                    str(estimate.estimated_rows),
                    f"{estimate.estimated_memory_mb:.3f}",
                    f"{estimate.estimated_write_mb:.3f}",
                    f"{estimate.estimated_seconds:.3f}",
                    estimate.risk_level,
                    estimate.recommendation,
                )
                for estimate in result.estimates
            ]
        )
        self.surface.set_plan_rows(
            [
                (
                    entry.table_name,
                    f"{entry.table_name}|stage={entry.stage}|chunk={entry.chunk_index}",
                    f"{entry.start_row}-{entry.end_row}",
                    str(entry.stage),
                    "-",
                    "planned",
                )
                for entry in result.chunk_plan
            ]
        )
        self._notify(
            f"Benchmark complete: chunks={result.chunk_summary.total_chunks}, rows={result.chunk_summary.total_rows}.",
            level="success",
            duration_ms=3600,
        )
        self._append_history(
            "benchmark_complete",
            self.surface.execution_mode_var.get(),
            False,
            result.chunk_summary.total_rows,
        )

    self.lifecycle.run_async(
        after=self.after,
        worker=worker,
        on_done=lambda payload: on_done(payload),
        on_failed=self._on_run_failed,
        on_cancelled=self._on_run_cancelled,
        phase_label="Running benchmark...",
        cancel_exceptions=(PerformanceRunCancelled,),
        dispatcher=self.ui_dispatch,
    )


def _start_generation(self, fallback_to_single_process: bool = False) -> None:
    if not self._ensure_project():
        return
    assert self.project is not None
    model = self._sync_viewmodel_from_vars()

    try:
        profile = run_hooks.build_profile_from_model(model)
    except ValueError as exc:
        self.error_surface.emit_exception_actionable(
            exc,
            location="Start generation",
            hint="fix invalid run profile values and retry",
            mode="mixed",
        )
        return

    output_mode = profile.output_mode
    output_csv_folder: str | None = None
    output_sqlite_path: str | None = None

    if output_mode in {"csv", "all"}:
        output_csv_folder = run_hooks.filedialog.askdirectory(title="Choose output folder for CSV export")
        if output_csv_folder in {None, ""}:
            self.shell.set_status("Run cancelled (no CSV output folder selected).")
            return
    if output_mode in {"sqlite", "all"}:
        output_sqlite_path = run_hooks.filedialog.asksaveasfilename(
            title="Choose SQLite output path",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
            initialfile="run_center_v2.db",
        )
        if output_sqlite_path in {None, ""}:
            self.shell.set_status("Run cancelled (no SQLite output path selected).")
            return

    def worker() -> MultiprocessRunResult:
        return run_hooks.run_generation_multiprocess(
            self.project,
            model,
            output_csv_folder=output_csv_folder,
            output_sqlite_path=output_sqlite_path,
            on_event=self.ui_dispatch.marshal(self._on_multiprocess_event),
            cancel_requested=self._is_cancel_requested,
            fallback_to_single_process=fallback_to_single_process,
        )

    def on_done(result: MultiprocessRunResult) -> None:
        self.lifecycle.transition_complete("Run complete")
        self.surface.set_plan_rows(
            [
                (
                    entry.table_name,
                    entry.partition_id,
                    f"{entry.start_row}-{entry.end_row}",
                    str(entry.stage),
                    str(entry.assigned_worker),
                    entry.status,
                )
                for entry in result.partition_plan
            ]
        )
        self.surface.set_failures_rows(
            [
                (
                    failure.partition_id,
                    failure.error,
                    str(failure.retry_count),
                    failure.action,
                )
                for failure in result.failures
            ]
        )

        csv_count = len(result.strategy_result.csv_paths)
        sqlite_rows = sum(result.strategy_result.sqlite_counts.values())
        self._notify(
            f"Run complete: rows={result.total_rows}, csv_files={csv_count}, sqlite_rows={sqlite_rows}, fallback={'yes' if result.fallback_used else 'no'}.",
            level="success",
            duration_ms=4200,
        )
        self._append_history("run_complete", result.mode, result.fallback_used, result.total_rows)

    label = "Running with fallback..." if fallback_to_single_process else "Running..."
    self.lifecycle.run_async(
        after=self.after,
        worker=worker,
        on_done=lambda payload: on_done(payload),
        on_failed=self._on_run_failed,
        on_cancelled=self._on_run_cancelled,
        phase_label=label,
        cancel_exceptions=(MultiprocessRunCancelled,),
        dispatcher=self.ui_dispatch,
    )

