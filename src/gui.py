import logging
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from config import AppConfig
from generator import generate_people
from storage_sqlite import init_db, insert_people


# ---- Logging handler that writes log records into a queue (thread-safe) ----
class QueueLogHandler(logging.Handler):
    """
    A logging.Handler that puts formatted log messages onto a queue.
    The GUI will periodically drain the queue and display messages.
    """
    def __init__(self, q: queue.Queue[str]) -> None:
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.q.put(msg)
        except Exception:
            # Never let logging crash the app.
            pass


class SyntheticDataGUI:
    def __init__(self, root: tk.Tk, cfg: AppConfig) -> None:
        self.root = root
        self.cfg = cfg

        self.root.title("Synthetic Data Generator (MVP)")
        self.root.geometry("900x600")

        # Queue for log lines and status messages from worker thread -> GUI thread
        self.log_queue: queue.Queue[str] = queue.Queue()

        # Setup UI-bound variables
        # These are Tkinter "Variable" objects; widgets can read/write them automatically.
        self.rows_var = tk.StringVar(value=str(cfg.default_rows))
        self.seed_var = tk.StringVar(value=str(cfg.seed))
        self.db_path_var = tk.StringVar(value=cfg.sqlite_db_path)
        self.status_var = tk.StringVar(value="Ready.")

        # Controls state
        self.is_running = False

        self._build_layout()
        self._attach_gui_logging()
        self._start_polling_log_queue()

    # ---------------- UI layout ----------------
    def _build_layout(self) -> None:
        # A Frame is a container used to organize widgets.
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        # Top "form" area
        form = ttk.LabelFrame(container, text="Generate synthetic data", padding=12)
        form.pack(fill=tk.X)

        # Grid layout: rows/cols inside the form
        # Grid is convenient for aligning labels/inputs in a table-like layout.
        form.columnconfigure(1, weight=1)  # let the Entry column expand

        ttk.Label(form, text="Rows to generate:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        rows_entry = ttk.Entry(form, textvariable=self.rows_var)
        rows_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="Seed (repeatable):").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        seed_entry = ttk.Entry(form, textvariable=self.seed_var)
        seed_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(form, text="SQLite DB path:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        db_entry = ttk.Entry(form, textvariable=self.db_path_var)
        db_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        browse_btn = ttk.Button(form, text="Browse…", command=self._browse_db_path)
        browse_btn.grid(row=2, column=2, sticky="ew", padx=6, pady=6)

        # Buttons row
        btn_row = ttk.Frame(form)
        btn_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(10, 6))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        self.run_btn = ttk.Button(btn_row, text="Generate + Insert into SQLite", command=self._on_run_clicked)
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.clear_btn = ttk.Button(btn_row, text="Clear log", command=self._clear_log)
        self.clear_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Progress bar (indeterminate: shows “working” without knowing percent)
        self.progress = ttk.Progressbar(form, mode="indeterminate")
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 0))

        # Status label
        status_frame = ttk.Frame(container, padding=(0, 10, 0, 10))
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=(8, 0))

        # Log display (ScrolledText provides a text box with a scrollbar)
        log_frame = ttk.LabelFrame(container, text="Log output", padding=12)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = ScrolledText(log_frame, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)

    # ---------------- Logging into the GUI ----------------
    def _attach_gui_logging(self) -> None:
        """
        Attach a logging handler that writes log lines into a queue.
        The GUI will display them in the ScrolledText area.
        """
        handler = QueueLogHandler(self.log_queue)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

        # Attach to root logger so logs from generator/storage/app show up
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

    def _start_polling_log_queue(self) -> None:
        """
        Tkinter can't be updated from background threads safely.
        So we poll the queue from the GUI thread using root.after().
        """
        self._drain_log_queue()
        # Schedule this function to run again after 100ms
        self.root.after(100, self._start_polling_log_queue)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)  # auto-scroll to bottom
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---------------- UI actions ----------------
    def _browse_db_path(self) -> None:
        """
        Use a file dialog to choose where the SQLite database will live.
        We use asksaveasfilename because the DB might not exist yet.
        """
        path = filedialog.asksaveasfilename(
            title="Choose SQLite database file",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path_var.set(path)

    def _on_run_clicked(self) -> None:
        if self.is_running:
            return

        # Validate inputs
        try:
            n = int(self.rows_var.get().strip())
            seed = int(self.seed_var.get().strip())
            db_path = self.db_path_var.get().strip()

            if n <= 0:
                raise ValueError("Rows must be > 0.")
            if not db_path:
                raise ValueError("DB path cannot be empty.")
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        # Start background work
        self.is_running = True
        self.status_var.set("Running…")
        self.run_btn.configure(state=tk.DISABLED)
        self.progress.start(10)  # 10ms step for animation

        worker = threading.Thread(
            target=self._worker_generate_and_insert,
            args=(n, seed, db_path),
            daemon=True,  # daemon thread will exit when app closes
        )
        worker.start()

    def _worker_generate_and_insert(self, n: int, seed: int, db_path: str) -> None:
        """
        Runs in a background thread. DO NOT touch Tkinter widgets here.
        Log messages are safe (they go into a queue).
        """
        logger = logging.getLogger("gui_worker")
        try:
            logger.info("Initializing DB: %s", db_path)
            init_db(db_path)

            logger.info("Generating %d rows (seed=%d)…", n, seed)
            rows = generate_people(n=n, seed=seed)

            logger.info("Inserting into SQLite…")
            inserted = insert_people(db_path, rows)

            logger.info("Done. Inserted %d rows.", inserted)

            # Schedule a GUI update back on the main thread
            self.root.after(0, lambda: self._on_job_finished(success=True, message=f"Inserted {inserted} rows."))
        except Exception as exc:
            logger.exception("Job failed: %s", exc)
            self.root.after(0, lambda: self._on_job_finished(success=False, message=str(exc)))

    def _on_job_finished(self, success: bool, message: str) -> None:
        """
        Runs on the GUI thread (scheduled via root.after).
        Safe to update widgets here.
        """
        self.progress.stop()
        self.run_btn.configure(state=tk.NORMAL)
        self.is_running = False

        if success:
            self.status_var.set("Completed.")
            messagebox.showinfo("Success", message)
        else:
            self.status_var.set("Failed.")
            messagebox.showerror("Error", message)


def start_gui(cfg: AppConfig) -> None:
    root = tk.Tk()
    # ttk is Tkinter's themed widget set; it looks nicer on Windows.
    # Use ttk widgets whenever possible.
    SyntheticDataGUI(root, cfg)
    root.mainloop()
