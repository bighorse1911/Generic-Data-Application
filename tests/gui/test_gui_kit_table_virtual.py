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

    def test_large_data_passthrough_and_auto_paging(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        adapter = VirtualTableAdapter(
            frame,
            columns=[
                TableColumnSpec("id", "ID", 80),
                TableColumnSpec("name", "Name", 140, stretch=True),
            ],
            height=6,
            large_data_enabled=True,
            large_data_threshold_rows=4,
            large_data_chunk_size=2,
            large_data_auto_pagination=True,
            large_data_auto_page_size=2,
        )

        rows = [{"id": i, "name": f"row-{i}"} for i in range(6)]
        adapter.set_rows(rows)
        for _ in range(30):
            self.root.update_idletasks()
            self.root.update()
        self.assertFalse(adapter.is_rendering)
        self.assertEqual(adapter.view.page_size, 2)
        self.assertEqual(len(adapter.tree.get_children()), 2)

        adapter.configure_large_data_mode(
            enabled=True,
            threshold_rows=2,
            chunk_size=1,
            auto_pagination=False,
        )
        adapter.set_rows([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}])
        adapter.cancel_pending_render()
        for _ in range(10):
            self.root.update_idletasks()
            self.root.update()
        self.assertFalse(adapter.is_rendering)


if __name__ == "__main__":
    unittest.main()


