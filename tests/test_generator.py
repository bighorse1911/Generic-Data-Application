# Paste below to run tests
# python -m unittest discover -s tests -p "test_*.py"


import unittest

from src.generator import generate_people

class TestGenerator(unittest.TestCase):
    def test_generate_people_count(self):
        rows = generate_people(10, seed=1)
        self.assertEqual(len(rows), 10)

    def test_generate_people_repeatable(self):
        a = generate_people(5, seed=42)
        b = generate_people(5, seed=42)
        self.assertEqual(a, b)

    def test_generate_people_invalid(self):
        with self.assertRaises(ValueError):
            generate_people(0, seed=1)

if __name__ == "__main__":
    unittest.main()
