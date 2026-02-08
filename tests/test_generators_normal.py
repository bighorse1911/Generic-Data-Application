import random
import unittest

from src.generators import get_generator, GenContext


class TestNormalGenerator(unittest.TestCase):
    def test_normal_respects_min_max_and_decimals(self):
        gen = get_generator("normal")
        # Use a mean far outside the clamp range to ensure clamping occurs
        params = {"mean": 1000.0, "stdev": 1.0, "decimals": 2, "min": 0.0, "max": 10.0}

        rng = random.Random(42)
        ctx = GenContext(row_index=1, table="t", row={}, rng=rng)
        v = gen(params, ctx)

        self.assertIsInstance(v, float)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 10.0)

    def test_normal_is_deterministic_with_seeded_rng(self):
        gen = get_generator("normal")
        params = {"mean": 0.0, "stdev": 1.0, "decimals": 3}

        rng1 = random.Random(12345)
        ctx1 = GenContext(row_index=1, table="t", row={}, rng=rng1)
        v1 = gen(params, ctx1)

        rng2 = random.Random(12345)
        ctx2 = GenContext(row_index=1, table="t", row={}, rng=rng2)
        v2 = gen(params, ctx2)

        self.assertEqual(v1, v2)


if __name__ == "__main__":
    unittest.main()
