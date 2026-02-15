import tkinter as tk
import unittest

from src.gui_kit.table_virtual import TableColumnSpec
from src.gui_kit.table_virtual import VirtualTableAdapter


class TestVirtualTableAdapter(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_set_rows_pagination_and_clear(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        adapter = VirtualTableAdapter(
            frame,
            columns=[
                TableColumnSpec("id", "ID", 80),
                TableColumnSpec("name", "Name", 140, stretch=True),
            ],
            height=6,
        )

        rows = [{"id": i, "name": f"row-{i}"} for i in range(5)]
        adapter.enable_pagination(page_size=2)
        adapter.set_rows(rows)
        self.assertEqual(len(adapter.tree.get_children()), 2)

        adapter.view.next_page()
        self.assertEqual(len(adapter.tree.get_children()), 2)

        adapter.disable_pagination()
        adapter.set_rows(rows)
        self.assertEqual(len(adapter.tree.get_children()), 5)

        adapter.clear()
        self.assertEqual(len(adapter.tree.get_children()), 0)


if __name__ == "__main__":
    unittest.main()
