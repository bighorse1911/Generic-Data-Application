import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from src.config import AppConfig
from src.generator import generate_people, PersonRow
from src.storage_sqlite import init_db, insert_people


class QueueLogHandler(logging.Handler):
    def __init__(self, q: queue.Queue[str]) -> None:
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put(self.format(record))
        except Exception:
            pass


class SyntheticDataScreen(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "object", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.is_running = False

        # UI variables (Entry widgets bind to these)
        self.rows_var = tk.StringVar(value=str(cfg.default_rows))
        self.seed_var = tk.StringVar(value=str(cfg.seed))
        self.db_path_var = tk.StringVar(value=cfg.sqlite_db_path)
        self.preview_rows_var = tk.StringVar(value="25")
        self.status_var = tk.StringVar(value="Ready.")

        # In-memory preview (so we can export without re-generating)
        self.preview_data: list[PersonRow] = []

        self._build_layout()
        self._attach_gui_logging()
        self._poll_log_queue()
        self._refresh_ui_state()


    def _build_layout(self) -> None:
        # Header with back button
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))

        ttk.Button(header, text="← Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Synthetic Data Generator", font=("Segoe UI", 16, "bold")).pack(side="left", padx=12)

        # Controls (left)
        controls = ttk.LabelFrame(self, text="Controls", padding=12)
        controls.pack(fill="x")

        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Rows to generate:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(controls, textvariable=self.rows_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(controls, text="Seed (repeatable):").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(controls, textvariable=self.seed_var).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ttk.Label(controls, text="SQLite DB path:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(controls, textvariable=self.db_path_var).grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(controls, text="Browse…", command=self._browse_db).grid(row=2, column=2, padx=6, pady=6)

        ttk.Label(controls, text="Preview rows:").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(controls, textvariable=self.preview_rows_var, width=10).grid(row=3, column=1, sticky="w", padx=6, pady=6)

        # Buttons row
        btns = ttk.Frame(controls)
        btns.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=(10, 6))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)

        self.generate_btn = ttk.Button(btns, text="Generate + Insert into SQLite", command=self._on_generate)
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.preview_btn = ttk.Button(btns, text="Generate Preview", command=self._on_preview)
        self.preview_btn.grid(row=0, column=1, sticky="ew", padx=6)

        self.export_btn = ttk.Button(btns, text="Export Preview to CSV", command=self._on_export_csv)
        self.export_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        self.export_btn.configure(state=tk.DISABLED)


        # Progress + status
        self.progress = ttk.Progressbar(controls, mode="indeterminate")
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 0))

        status = ttk.Frame(self, padding=(0, 10, 0, 10))
        status.pack(fill="x")
        ttk.Label(status, text="Status:").pack(side="left")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=(8, 0))

        # Main area: preview table + logs (stacked)
        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill="both", expand=True)

        preview_frame = ttk.LabelFrame(paned, text="Preview", padding=8)
        log_frame = ttk.LabelFrame(paned, text="Log output", padding=8)
        paned.add(preview_frame, weight=3)
        paned.add(log_frame, weight=2)

        # Treeview table
        columns = ("person_id", "first_name", "last_name", "email", "age", "created_at")
        self.tree = ttk.Treeview(preview_frame, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140, anchor="w")

        self.tree.column("person_id", width=80, anchor="e")
        self.tree.column("age", width=80, anchor="e")

        yscroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        # Log window
        self.log_text = ScrolledText(log_frame, height=12, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state=tk.DISABLED)

        ttk.Button(log_frame, text="Clear log", command=self._clear_log).pack(anchor="e", pady=(6, 0))

    # ---------- Logging ----------
    def _attach_gui_logging(self) -> None:
        handler = QueueLogHandler(self.log_queue)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )

        root_logger = logging.getLogger()

        # Only attach if we haven't already attached a QueueLogHandler.
        # This prevents duplicated logs if the screen gets created again.
        already_attached = any(isinstance(h, QueueLogHandler) for h in root_logger.handlers)
        if not already_attached:
            root_logger.addHandler(handler)



    def _poll_log_queue(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)

        self.after(100, self._poll_log_queue)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---------- Helpers ----------
    def _set_running(self, running: bool, status: str) -> None:
        self.is_running = running
        self.status_var.set(status)
        self._refresh_ui_state()


    def _read_inputs(self) -> tuple[int, int, str, int]:
        """
        Convert Entry text to integers and validate.
        If invalid, raise ValueError with a helpful message.
        """
        n = int(self.rows_var.get().strip())
        seed = int(self.seed_var.get().strip())
        db_path = self.db_path_var.get().strip()
        preview_n = int(self.preview_rows_var.get().strip())

        if n <= 0:
            raise ValueError("Rows to generate must be > 0.")
        if preview_n <= 0:
            raise ValueError("Preview rows must be > 0.")
        if not db_path:
            raise ValueError("SQLite DB path cannot be empty.")

        return n, seed, db_path, preview_n

    def _browse_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose SQLite database file",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path_var.set(path)

    def _refresh_table(self, rows: list[PersonRow]) -> None:
        # Clear existing table rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Insert new rows
        for r in rows:
            self.tree.insert(
                "",
                tk.END,
                values=(r.person_id, r.first_name, r.last_name, r.email, r.age, r.created_at),
            )

    # ---------- Actions ----------
    def _on_preview(self) -> None:
        if self.is_running:
            return

        try:
            n, seed, _db_path, preview_n = self._read_inputs()
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        # Preview doesn’t need a worker thread unless you preview huge amounts.
        # But we’ll keep it responsive anyway (good habit).
        self._set_running(True, "Generating preview…")

        worker = threading.Thread(
            target=self._worker_preview,
            args=(min(preview_n, n), seed),
            daemon=True,
        )
        worker.start()

    def _worker_preview(self, preview_n: int, seed: int) -> None:
        logger = logging.getLogger("preview")
        try:
            logger.info("Generating preview: %d rows (seed=%d)", preview_n, seed)
            rows = generate_people(n=preview_n, seed=seed)

            # Schedule GUI update on the main thread
            self.after(0, lambda: self._on_preview_done(rows))
        except Exception as exc:
            logger.exception("Preview failed: %s", exc)
            self.after(0, lambda: self._on_fail(str(exc)))

    def _on_preview_done(self, rows: list[PersonRow]) -> None:
        self.preview_data = rows
        self._refresh_table(rows)
        self._set_running(False, f"Preview generated ({len(rows)} rows).")


    def _on_generate(self) -> None:
        if self.is_running:
            return

        try:
            n, seed, db_path, _preview_n = self._read_inputs()
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self._set_running(True, "Generating + inserting into SQLite…")

        worker = threading.Thread(
            target=self._worker_generate_insert,
            args=(n, seed, db_path),
            daemon=True,
        )
        worker.start()

    def _worker_generate_insert(self, n: int, seed: int, db_path: str) -> None:
        logger = logging.getLogger("generate_insert")
        try:
            logger.info("Initializing DB: %s", db_path)
            init_db(db_path)

            logger.info("Generating %d rows (seed=%d)…", n, seed)
            rows = generate_people(n=n, seed=seed)

            logger.info("Inserting into SQLite…")
            inserted = insert_people(db_path, rows)

            self.after(0, lambda: self._on_generate_done(inserted, db_path))
        except Exception as exc:
            logger.exception("Generate+Insert failed: %s", exc)
            self.after(0, lambda: self._on_fail(str(exc)))

    def _on_generate_done(self, inserted: int, db_path: str) -> None:
        self._set_running(False, f"Completed. Inserted {inserted} rows into {db_path}")
        messagebox.showinfo("Success", f"Inserted {inserted} rows into:\n{db_path}")

    def _on_export_csv(self) -> None:
        if not self.preview_data:
            messagebox.showwarning("No preview", "Generate a preview first, then export.")
            return

        path = filedialog.asksaveasfilename(
            title="Save preview as CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        # We’ll write CSV using only standard library
        try:
            import csv

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["person_id", "first_name", "last_name", "email", "age", "created_at"])
                for r in self.preview_data:
                    writer.writerow([r.person_id, r.first_name, r.last_name, r.email, r.age, r.created_at])

            self.status_var.set(f"Exported preview to {path}")
            messagebox.showinfo("Exported", f"Saved preview CSV:\n{path}")
        except Exception as exc:
            logging.getLogger("export").exception("Export failed: %s", exc)
            messagebox.showerror("Export failed", str(exc))

    def _on_fail(self, message: str) -> None:
        self._set_running(False, "Failed.")
        messagebox.showerror("Error", message)

    def _refresh_ui_state(self) -> None:
        """
        Single place that decides what the UI should look like
        based on the current app state.
        """
        has_preview = len(self.preview_data) > 0

        # Buttons
        self.generate_btn.configure(state=(tk.DISABLED if self.is_running else tk.NORMAL))
        self.preview_btn.configure(state=(tk.DISABLED if self.is_running else tk.NORMAL))
        self.export_btn.configure(
            state=(tk.DISABLED if (self.is_running or not has_preview) else tk.NORMAL)
        )

        # Progress bar
        if self.is_running:
            # Only start if not already moving (safe to call repeatedly)
            self.progress.start(10)
        else:
            self.progress.stop()


