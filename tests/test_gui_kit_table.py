import unittest

from src.gui_kit.table import estimate_column_widths, normalize_rows


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


if __name__ == "__main__":
    unittest.main()
