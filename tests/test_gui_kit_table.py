import tkinter as tk
import unittest

from src.gui_kit.table import TableView, estimate_column_widths, normalize_rows, paginate_rows


class TestNormalizeRows(unittest.TestCase):
    def test_dict_rows_infer_columns(self):
        cols, rows = normalize_rows(
            [
                {"name": "alice", "age": 30},
                {"name": "bob", "age": 40},
            ]
        )
        self.assertEqual(cols, ["name", "age"])
        self.assertEqual(rows, [["alice", 30], ["bob", 40]])

    def test_sequence_rows_pads_to_column_count(self):
        cols, rows = normalize_rows([[1], [2, 3]], columns=["a", "b"])
        self.assertEqual(cols, ["a", "b"])
        self.assertEqual(rows, [[1, ""], [2, 3]])


class TestEstimateColumnWidths(unittest.TestCase):
    def test_widths_respect_min_max(self):
        widths = estimate_column_widths(
            ["id", "description"],
            [[1, "short"], [2, "x" * 200]],
            min_px=80,
            max_px=320,
        )
        self.assertGreaterEqual(widths["id"], 80)
        self.assertEqual(widths["description"], 320)


class TestPaginateRows(unittest.TestCase):
    def test_paginate_rows_normalizes_out_of_range_page_index(self):
        rows = [[1], [2], [3], [4], [5]]
        page_rows, page_index, total_pages = paginate_rows(rows, page_size=2, page_index=99)
        self.assertEqual(page_rows, [[5]])
        self.assertEqual(page_index, 2)
        self.assertEqual(total_pages, 3)

    def test_paginate_rows_handles_empty_rows(self):
        page_rows, page_index, total_pages = paginate_rows([], page_size=10, page_index=0)
        self.assertEqual(page_rows, [])
        self.assertEqual(page_index, 0)
        self.assertEqual(total_pages, 0)

    def test_paginate_rows_requires_positive_page_size(self):
        with self.assertRaises(ValueError) as ctx:
            paginate_rows([[1]], page_size=0, page_index=0)
        self.assertIn("page_size must be > 0", str(ctx.exception))


class TestTableViewLargeData(unittest.TestCase):
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

    def _drain(self, *, rounds: int = 40) -> None:
        for _ in range(rounds):
            if not self.root.winfo_exists():
                return
            self.root.update_idletasks()
            self.root.update()

    def test_large_data_mode_chunks_and_completes_render(self):
        table = TableView(self.root, height=4)
        table.pack(fill="both", expand=True)
        table.set_columns(["id"])
        table.configure_large_data_mode(
            enabled=True,
            threshold_rows=10,
            chunk_size=3,
            auto_pagination=False,
        )

        table.set_rows([[idx] for idx in range(12)])
        self.assertTrue(table.is_rendering)
        self._drain()
        self.assertFalse(table.is_rendering)
        self.assertEqual(len(table.tree.get_children()), 12)

    def test_reentrant_set_rows_drops_stale_render(self):
        table = TableView(self.root, height=4)
        table.pack(fill="both", expand=True)
        table.set_columns(["id"])
        table.configure_large_data_mode(
            enabled=True,
            threshold_rows=2,
            chunk_size=1,
            auto_pagination=False,
        )

        table.set_rows([[idx] for idx in range(30)])
        table.set_rows([[101], [102], [103]])
        self._drain()
        values = [int(table.tree.item(item, "values")[0]) for item in table.tree.get_children()]
        self.assertEqual(values, [101, 102, 103])

    def test_auto_pagination_applies_and_recovers_by_threshold(self):
        table = TableView(self.root, height=4)
        table.pack(fill="both", expand=True)
        table.set_columns(["id"])
        table.configure_large_data_mode(
            enabled=True,
            threshold_rows=5,
            chunk_size=2,
            auto_pagination=True,
            auto_page_size=2,
        )

        table.set_rows([[idx] for idx in range(6)])
        self._drain()
        self.assertTrue(table._pagination_enabled)
        self.assertEqual(table.page_size, 2)
        self.assertEqual(len(table.tree.get_children()), 2)

        table.set_rows([[1], [2], [3]])
        self._drain()
        self.assertFalse(table._pagination_enabled)
        self.assertEqual(len(table.tree.get_children()), 3)

    def test_clear_cancels_pending_render(self):
        table = TableView(self.root, height=4)
        table.pack(fill="both", expand=True)
        table.set_columns(["id"])
        table.configure_large_data_mode(
            enabled=True,
            threshold_rows=2,
            chunk_size=1,
            auto_pagination=False,
        )

        table.set_rows([[idx] for idx in range(100)])
        self.assertTrue(table.is_rendering)
        table.clear()
        self._drain()
        self.assertFalse(table.is_rendering)
        self.assertEqual(len(table.tree.get_children()), 0)


if __name__ == "__main__":
    unittest.main()


