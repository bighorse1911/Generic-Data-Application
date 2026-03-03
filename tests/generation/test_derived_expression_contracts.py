from __future__ import annotations

import unittest

import src.derived_expression as derived_expression


class TestDerivedExpressionContracts(unittest.TestCase):
    def test_facade_exports_required_symbols(self) -> None:
        required = (
            "CompiledDerivedExpression",
            "compile_derived_expression",
            "evaluate_derived_expression",
            "extract_derived_expression_references",
            "is_iso_date_text",
            "is_iso_datetime_text",
            "MAX_EXPRESSION_LENGTH",
            "MAX_EXPRESSION_NODES",
            "MAX_EXPRESSION_DEPTH",
        )
        for name in required:
            self.assertTrue(hasattr(derived_expression, name), f"Missing derived_expression export: {name}")

    def test_facade_keeps_private_compat_symbols(self) -> None:
        required = (
            "_ExpressionValidator",
            "_ExpressionEvaluator",
            "_expression_error",
        )
        for name in required:
            self.assertTrue(hasattr(derived_expression, name), f"Missing derived_expression compat symbol: {name}")

    def test_error_text_parity_samples(self) -> None:
        expected_messages = {
            "syntax": (
                "Derived expression test: expression syntax is invalid (syntax error). "
                "Fix: use a valid expression with allowed operators/functions."
            ),
            "unsupported_fn": (
                "Derived expression test: function 'unknown_fn' is not allowed. "
                "Fix: use one of: abs, coalesce, col, concat, if_else, is_null, max, min, round, "
                "to_bool, to_decimal, to_int, to_text."
            ),
            "missing_ref": (
                "Derived expression test: expression reference 'fee' is not available in the current row context. "
                "Fix: add the source column to depends_on and ensure it exists."
            ),
            "divide_zero": (
                "Derived expression test: division by zero in '/'. "
                "Fix: ensure the denominator is non-zero before division."
            ),
            "bad_cast": (
                "Derived expression test: to_int(...) could not parse 'abc'. "
                "Fix: provide an integer-like string such as '42'."
            ),
        }

        with self.assertRaises(ValueError) as syntax_ctx:
            derived_expression.compile_derived_expression("1 +", location="Derived expression test")
        self.assertEqual(str(syntax_ctx.exception), expected_messages["syntax"])

        with self.assertRaises(ValueError) as fn_ctx:
            derived_expression.compile_derived_expression("unknown_fn(base)", location="Derived expression test")
        self.assertEqual(str(fn_ctx.exception), expected_messages["unsupported_fn"])

        compiled_missing = derived_expression.compile_derived_expression(
            "base + fee",
            location="Derived expression test",
        )
        with self.assertRaises(ValueError) as missing_ctx:
            derived_expression.evaluate_derived_expression(
                compiled_missing,
                row={"base": 10},
                location="Derived expression test",
            )
        self.assertEqual(str(missing_ctx.exception), expected_messages["missing_ref"])

        compiled_divide = derived_expression.compile_derived_expression(
            "10 / denom",
            location="Derived expression test",
        )
        with self.assertRaises(ValueError) as divide_ctx:
            derived_expression.evaluate_derived_expression(
                compiled_divide,
                row={"denom": 0},
                location="Derived expression test",
            )
        self.assertEqual(str(divide_ctx.exception), expected_messages["divide_zero"])

        compiled_cast = derived_expression.compile_derived_expression(
            "to_int(raw)",
            location="Derived expression test",
        )
        with self.assertRaises(ValueError) as cast_ctx:
            derived_expression.evaluate_derived_expression(
                compiled_cast,
                row={"raw": "abc"},
                location="Derived expression test",
            )
        self.assertEqual(str(cast_ctx.exception), expected_messages["bad_cast"])


if __name__ == "__main__":
    unittest.main()

