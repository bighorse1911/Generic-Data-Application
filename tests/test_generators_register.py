import unittest

from src import generators


class TestRegisterGuard(unittest.TestCase):
    def tearDown(self) -> None:
        # remove any test keys we added to keep registry clean
        generators.REGISTRY.pop("__test_unique_gen__", None)

    def test_duplicate_register_raises(self):
        # ensure unique name not present
        generators.REGISTRY.pop("__test_unique_gen__", None)

        @generators.register("__test_unique_gen__")
        def g1(params, ctx):
            return "ok"

        with self.assertRaises(KeyError):
            @generators.register("__test_unique_gen__")
            def g2(params, ctx):
                return "bad"


if __name__ == "__main__":
    unittest.main()
