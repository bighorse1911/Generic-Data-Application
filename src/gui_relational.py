import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.config import AppConfig
from src.generator_relational import generate_relational_data
from src.storage_sqlite_relational import (
    init_relational_db,
    insert_customers,
    insert_orders,
    insert_order_items,
)

logger = logging.getLogger("gui_relational")


class RelationalDataScreen(ttk.Frame):
    def __init__(self, parent: tk.Widget, app: "object", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.is_running = False

        # Inputs
        self.db_path_var = tk.StringVar(value=cfg.sqlite_db_path)
        self.customers_var = tk.StringVar(value="100")
        self.orders_min_var = tk.StringVar(value="1")
        self.orders_max_var = tk.StringVar(value="5")
        self.items_min_var = tk.StringVar(value="1")
        self.items_max_var = tk.StringVar(value="6")
        self.seed_var = tk.StringVar(value=str(cfg.seed))
        self.status_var = tk.StringVar(value="Ready.")

        self._build()

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        ttk.Button(header, text="← Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Relational Generator (Customers → Orders → Items)", font=("Segoe UI", 16, "bold")).pack(side="left", padx=12)

        form = ttk.LabelFrame(self, text="Parameters", padding=12)
        form.pack(fill="x")

        form.columnconfigure(1, weight=1)

        def row(label: str, var: tk.StringVar, r: int, browse: bool = False) -> None:
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", padx=6, pady=6)
            ttk.Entry(form, textvariable=var).grid(row=r, column=1, sticky="ew", padx=6, pady=6)
            if browse:
                ttk.Button(form, text="Browse…", command=self._browse_db).grid(row=r, column=2, padx=6, pady=6)

        row("SQLite DB path:", self.db_path_var, 0, browse=True)
        row("Customers:", self.customers_var, 1)
        row("Orders per customer (min):", self.orders_min_var, 2)
        row("Orders per customer (max):", self.orders_max_var, 3)
        row("Items per order (min):", self.items_min_var, 4)
        row("Items per order (max):", self.items_max_var, 5)
        row("Seed:", self.seed_var, 6)

        btn = ttk.Button(form, text="Generate + Insert Relational Data", command=self._on_run)
        btn.grid(row=7, column=0, columnspan=3, sticky="ew", padx=6, pady=(12, 0))
        self.run_btn = btn

        self.progress = ttk.Progressbar(form, mode="indeterminate")
        self.progress.grid(row=8, column=0, columnspan=3, sticky="ew", padx=6, pady=(8, 0))

        status = ttk.Frame(self, padding=(0, 10, 0, 0))
        status.pack(fill="x")
        ttk.Label(status, text="Status:").pack(side="left")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=(8, 0))

    def _browse_db(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose SQLite database file",
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path_var.set(path)

    def _read_int(self, var: tk.StringVar, name: str) -> int:
        try:
            return int(var.get().strip())
        except Exception:
            raise ValueError(f"{name} must be an integer")

    def _on_run(self) -> None:
        if self.is_running:
            return

        try:
            db_path = self.db_path_var.get().strip()
            if not db_path:
                raise ValueError("DB path cannot be empty")

            num_customers = self._read_int(self.customers_var, "Customers")
            orders_min = self._read_int(self.orders_min_var, "Orders min")
            orders_max = self._read_int(self.orders_max_var, "Orders max")
            items_min = self._read_int(self.items_min_var, "Items min")
            items_max = self._read_int(self.items_max_var, "Items max")
            seed = self._read_int(self.seed_var, "Seed")

        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.is_running = True
        self.run_btn.configure(state=tk.DISABLED)
        self.status_var.set("Running…")
        self.progress.start(10)

        t = threading.Thread(
            target=self._worker,
            args=(db_path, num_customers, orders_min, orders_max, items_min, items_max, seed),
            daemon=True,
        )
        t.start()

    def _worker(self, db_path: str, num_customers: int, orders_min: int, orders_max: int, items_min: int, items_max: int, seed: int) -> None:
        try:
            init_relational_db(db_path)

            data = generate_relational_data(
                num_customers=num_customers,
                orders_per_customer_min=orders_min,
                orders_per_customer_max=orders_max,
                items_per_order_min=items_min,
                items_per_order_max=items_max,
                seed=seed,
            )

            # Insert in FK-safe order
            c = insert_customers(db_path, data.customers)
            o = insert_orders(db_path, data.orders)
            i = insert_order_items(db_path, data.order_items)

            self.after(0, lambda: self._done(True, f"Inserted customers={c}, orders={o}, items={i}"))
        except Exception as exc:
            logger.exception("Relational job failed: %s", exc)
            self.after(0, lambda: self._done(False, str(exc)))

    def _done(self, ok: bool, msg: str) -> None:
        self.progress.stop()
        self.run_btn.configure(state=tk.NORMAL)
        self.is_running = False

        if ok:
            self.status_var.set("Completed.")
            messagebox.showinfo("Success", msg)
        else:
            self.status_var.set("Failed.")
            messagebox.showerror("Error", msg)
