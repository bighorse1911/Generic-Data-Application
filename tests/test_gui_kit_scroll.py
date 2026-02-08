import unittest

from src.gui_kit.scroll import wheel_units_from_delta


class TestWheelUnitsFromDelta(unittest.TestCase):
    def test_zero_delta(self):
        self.assertEqual(wheel_units_from_delta(0), 0)

    def test_windows_notch_direction(self):
        self.assertEqual(wheel_units_from_delta(120), -1)
        self.assertEqual(wheel_units_from_delta(-120), 1)

    def test_small_trackpad_delta(self):
        self.assertEqual(wheel_units_from_delta(15), -1)
        self.assertEqual(wheel_units_from_delta(-15), 1)

    def test_multiple_notches(self):
        self.assertEqual(wheel_units_from_delta(240), -2)
        self.assertEqual(wheel_units_from_delta(-360), 3)


if __name__ == "__main__":
    unittest.main()
