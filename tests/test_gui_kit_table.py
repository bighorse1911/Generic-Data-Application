import unittest

from src.gui_kit.table import estimate_column_widths, normalize_rows, paginate_rows


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


if __name__ == "__main__":
    unittest.main()
