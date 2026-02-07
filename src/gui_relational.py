import logging
import threading
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src.config import AppConfig
from src.generator_relational import generate_relational_data
from src.storage_sqlite_relational import init_relational_db, insert_relational_data


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
        self.preview_data = None  # will hold generated relational data
        self.max_display_var = tk.StringVar(value="500")


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
        row("Max rows shown per tab:", self.max_display_var, 7)
        # Buttons row
        btns = ttk.Frame(form)
        btns.grid(row=7, column=0, columnspan=3, sticky="ew", padx=6, pady=(12, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)

        self.run_btn = ttk.Button(btns, text="Generate + Insert into SQLite", command=self._on_run)
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.preview_btn = ttk.Button(btns, text="Generate Preview (no DB)", command=self._on_preview)
        self.preview_btn.grid(row=0, column=1, sticky="ew", padx=6)

        self.preview_join_btn = ttk.Button(btns, text="Preview joined rows (from DB)", command=self._preview_join)
        self.preview_join_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        # Export button (disabled until preview exists)
        self.export_btn = ttk.Button(form, text="Export Preview to CSV", command=self._export_preview_csv)
        self.export_btn.grid(row=8, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 0))
        self.export_btn.configure(state=tk.DISABLED)

        self.progress = ttk.Progressbar(form, mode="indeterminate")
        self.progress.grid(row=9, column=0, columnspan=3, sticky="ew", padx=6, pady=(8, 0))


        status = ttk.Frame(self, padding=(0, 10, 0, 0))
        status.pack(fill="x")
        ttk.Label(status, text="Status:").pack(side="left")
        ttk.Label(status, textvariable=self.status_var).pack(side="left", padx=(8, 0))
        # --- Preview tables area ---
        tables_frame = ttk.LabelFrame(self, text="Preview tables (in-memory)", padding=8)
        tables_frame.pack(fill="both", expand=True, pady=(10, 0))

        # Notebook = tabs
        self.notebook = ttk.Notebook(tables_frame)
        self.notebook.pack(fill="both", expand=True)

        tab_customers = ttk.Frame(self.notebook, padding=6)
        tab_orders = ttk.Frame(self.notebook, padding=6)
        tab_items = ttk.Frame(self.notebook, padding=6)
        tab_join = ttk.Frame(self.notebook, padding=6)
        self.tab_join = tab_join

        self.notebook.add(tab_customers, text="Customers")
        self.notebook.add(tab_orders, text="Orders")
        self.notebook.add(tab_items, text="Order Items")
        self.notebook.add(tab_join, text="Join Preview")

        # Create Treeviews
        self.customers_tree = self._make_treeview(
            tab_customers,
            columns=[
                ("customer_id", 90, "e"),
                ("full_name", 220, "w"),
                ("email", 260, "w"),
                ("created_at", 200, "w"),
            ],
        )

        self.orders_tree = self._make_treeview(
            tab_orders,
            columns=[
                ("order_id", 90, "e"),
                ("customer_id", 110, "e"),
                ("order_date", 200, "w"),
                ("status", 120, "w"),
            ],
        )

        self.items_tree = self._make_treeview(
            tab_items,
            columns=[
                ("order_item_id", 110, "e"),
                ("order_id", 90, "e"),
                ("sku", 170, "w"),
                ("quantity", 90, "e"),
                ("unit_price", 110, "e"),
            ],
        )

        self.join_tree = self._make_treeview(
            tab_join,
            columns=[
                ("customer_id", 90, "e"),
                ("full_name", 220, "w"),
                ("order_id", 90, "e"),
                ("status", 110, "w"),
                ("sku", 170, "w"),
                ("quantity", 90, "e"),
                ("unit_price", 110, "e"),
            ],
        )


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

        # ✅ NEW: centralized UI state handling
        self._set_running(True, "Running…")

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

            c, o, i = insert_relational_data(db_path, data)
            self.after(0, lambda: self._done(True, f"Inserted customers={c}, orders={o}, items={i}"))


            self.after(0, lambda: self._done(True, f"Inserted customers={c}, orders={o}, items={i}"))
        except Exception as exc:
            logger.exception("Relational job failed: %s", exc)
            self.after(0, lambda: self._done(False, str(exc)))

    def _done(self, ok: bool, msg: str) -> None:
        self._set_running(False, "Completed." if ok else "Failed.")

        if ok:
            messagebox.showinfo("Success", msg)
        else:
            messagebox.showerror("Error", msg)

    
    def _preview_join(self) -> None:
        db_path = self.db_path_var.get().strip()
        if not db_path:
            messagebox.showerror("Missing DB path", "Choose a database path first.")
            return

        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys = ON;")
            max_display = self._get_max_display()

            join_sql = f"""
            SELECT
                c.customer_id,
                c.full_name,
                o.order_id,
                o.status,
                i.sku,
                i.quantity,
                i.unit_price
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id
            JOIN order_items i ON i.order_id = o.order_id
            ORDER BY c.customer_id, o.order_id, i.order_item_id
            LIMIT {max_display};
            """

            rows = conn.execute(join_sql).fetchall()
            conn.close()

            # Format unit_price nicely
            formatted = []
            for r in rows:
                formatted.append((r[0], r[1], r[2], r[3], r[4], r[5], f"{float(r[6]):.2f}"))

            self._fill_tree(self.join_tree, formatted)

            # Optional: switch to Join tab
            if hasattr(self, "tab_join"):
                self.notebook.select(self.tab_join)

            self.status_var.set(f"Loaded {len(formatted)} joined rows from DB.")
        except Exception as exc:
            messagebox.showerror("Preview failed", str(exc))



    def _show_text_popup(self, title: str, text: str) -> None:
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("950x500")

        box = tk.Text(win, wrap="none")
        box.insert("1.0", text)
        box.configure(state=tk.DISABLED)

        yscroll = ttk.Scrollbar(win, orient="vertical", command=box.yview)
        xscroll = ttk.Scrollbar(win, orient="horizontal", command=box.xview)
        box.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        box.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)
    def _set_running(self, running: bool, status: str) -> None:
        self.is_running = running
        self.status_var.set(status)

        state = (tk.DISABLED if running else tk.NORMAL)
        self.run_btn.configure(state=state)
        self.preview_btn.configure(state=state)
        self.preview_join_btn.configure(state=state)

        # Export only enabled when not running and preview exists
        if running:
            self.export_btn.configure(state=tk.DISABLED)
            self.progress.start(10)
        else:
            self.progress.stop()
            if self.preview_data is not None:
                self.export_btn.configure(state=tk.NORMAL)
            else:
                self.export_btn.configure(state=tk.DISABLED)


    def _on_preview(self) -> None:
        if self.is_running:
            return

        try:
            # same parsing as _on_run
            db_path = self.db_path_var.get().strip()  # not required for preview, but we’ll reuse it later
            num_customers = self._read_int(self.customers_var, "Customers")
            orders_min = self._read_int(self.orders_min_var, "Orders min")
            orders_max = self._read_int(self.orders_max_var, "Orders max")
            items_min = self._read_int(self.items_min_var, "Items min")
            items_max = self._read_int(self.items_max_var, "Items max")
            seed = self._read_int(self.seed_var, "Seed")
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self._set_running(True, "Generating preview (in memory)…")

        t = threading.Thread(
            target=self._worker_preview,
            args=(num_customers, orders_min, orders_max, items_min, items_max, seed),
            daemon=True,
        )
        t.start()


    def _worker_preview(self, num_customers: int, orders_min: int, orders_max: int, items_min: int, items_max: int, seed: int) -> None:
        try:
            data = generate_relational_data(
                num_customers=num_customers,
                orders_per_customer_min=orders_min,
                orders_per_customer_max=orders_max,
                items_per_order_min=items_min,
                items_per_order_max=items_max,
                seed=seed,
            )
            self.after(0, lambda: self._on_preview_done(data))
        except Exception as exc:
            logger.exception("Preview generation failed: %s", exc)
            self.after(0, lambda: self._done(False, str(exc)))


    def _on_preview_done(self, data) -> None:
        try:
            max_display = self._get_max_display()
        except Exception as exc:
            messagebox.showerror("Invalid display limit", str(exc))
            self._set_running(False, "Failed.")
            return

        self.preview_data = data

        # Fill customers
        customers_rows = [
            (c.customer_id, c.full_name, c.email, c.created_at)
            for c in data.customers[:max_display]
        ]
        self._fill_tree(self.customers_tree, customers_rows)

        # Fill orders
        orders_rows = [
            (o.order_id, o.customer_id, o.order_date, o.status)
            for o in data.orders[:max_display]
        ]
        self._fill_tree(self.orders_tree, orders_rows)


        # Fill items
        items_rows = [
            (it.order_item_id, it.order_id, it.sku, it.quantity, f"{it.unit_price:.2f}")
            for it in data.order_items[:max_display]
        ]
        self._fill_tree(self.items_tree, items_rows)


        # Fill join preview (in memory)
        cust_by_id = {c.customer_id: c for c in data.customers}
        order_by_id = {o.order_id: o for o in data.orders}

        join_limit = min(max_display, 2000)


        join_rows = []
        for it in data.order_items[:join_limit]:
            o = order_by_id[it.order_id]
            c = cust_by_id[o.customer_id]
            join_rows.append((c.customer_id, c.full_name, o.order_id, o.status, it.sku, it.quantity, f"{it.unit_price:.2f}"))

        self._fill_tree(self.join_tree, join_rows)


        # Switch to the Join tab automatically (optional, feels nice)
        self.notebook.select(self.join_tree.master.master)  # safe: join_tree -> frame -> tab

        self._set_running(False, "Preview ready. You can export to CSV.")




    def _export_preview_csv(self) -> None:
        if self.preview_data is None:
            messagebox.showwarning("No preview", "Generate a preview first, then export.")
            return

        folder = filedialog.askdirectory(title="Choose folder to export CSV files")
        if not folder:
            return

        try:
            import csv
            import os

            data = self.preview_data

            customers_path = os.path.join(folder, "customers.csv")
            orders_path = os.path.join(folder, "orders.csv")
            items_path = os.path.join(folder, "order_items.csv")
            joined_path = os.path.join(folder, "joined_preview.csv")

            # customers.csv
            with open(customers_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["customer_id", "full_name", "email", "created_at"])
                for c in data.customers:
                    w.writerow([c.customer_id, c.full_name, c.email, c.created_at])

            # orders.csv
            with open(orders_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["order_id", "customer_id", "order_date", "status"])
                for o in data.orders:
                    w.writerow([o.order_id, o.customer_id, o.order_date, o.status])

            # order_items.csv
            with open(items_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["order_item_id", "order_id", "sku", "quantity", "unit_price"])
                for it in data.order_items:
                    w.writerow([it.order_item_id, it.order_id, it.sku, it.quantity, it.unit_price])

            # joined_preview.csv (flattened; useful for quick inspection)
            cust_by_id = {c.customer_id: c for c in data.customers}
            order_by_id = {o.order_id: o for o in data.orders}

            with open(joined_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["customer_id", "full_name", "email", "order_id", "order_date", "status",
                            "order_item_id", "sku", "quantity", "unit_price"])
                for it in data.order_items:
                    o = order_by_id[it.order_id]
                    c = cust_by_id[o.customer_id]
                    w.writerow([c.customer_id, c.full_name, c.email, o.order_id, o.order_date, o.status,
                                it.order_item_id, it.sku, it.quantity, it.unit_price])

            self.status_var.set(f"Exported CSVs to {folder}")
            messagebox.showinfo(
                "Export complete",
                "Exported:\n"
                f"- {customers_path}\n"
                f"- {orders_path}\n"
                f"- {items_path}\n"
                f"- {joined_path}"
            )
        except Exception as exc:
            logger.exception("Export failed: %s", exc)
            messagebox.showerror("Export failed", str(exc))
    def _make_treeview(self, parent: ttk.Frame, columns: list[tuple[str, int, str]]) -> ttk.Treeview:
        """
        Create a Treeview with vertical scrollbar.
        columns: list of (column_name, width_px, anchor) where anchor is 'w'/'e'/'center'.
        """
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        col_ids = [c[0] for c in columns]
        tree = ttk.Treeview(frame, columns=col_ids, show="headings")

        for name, width, anchor in columns:
            tree.heading(name, text=name)
            tree.column(name, width=width, anchor=anchor, stretch=True)

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)

        tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        return tree

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def _fill_tree(self, tree: ttk.Treeview, rows: list[tuple]) -> None:
        self._clear_tree(tree)
        for r in rows:
            tree.insert("", tk.END, values=r)


    def _get_max_display(self) -> int:
        n = self._read_int(self.max_display_var, "Max rows shown per tab")
        if n <= 0:
            raise ValueError("Max rows shown per tab must be > 0.")
        if n > 50_000:
            # guardrail; Treeview with huge row counts is painful
            raise ValueError("Max rows shown per tab is too large (max 50000).")
        return n
