from __future__ import annotations

import ast
import math
from typing import Any, Mapping

from src.derived_expression_common import _expression_error, _is_number


class _ExpressionEvaluator:
    def __init__(self, *, row: Mapping[str, Any], location: str) -> None:
        self.row = row
        self.location = location

    def evaluate(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id not in self.row:
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"expression reference '{node.id}' is not available in the current row context",
                        "add the source column to depends_on and ensure it exists",
                    )
                )
            return self.row[node.id]

        if isinstance(node, ast.BinOp):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            return self._eval_binary(node.op, left, right)

        if isinstance(node, ast.UnaryOp):
            value = self.evaluate(node.operand)
            return self._eval_unary(node.op, value)

        if isinstance(node, ast.BoolOp):
            return self._eval_bool(node.op, node.values)

        if isinstance(node, ast.Compare):
            return self._eval_compare(node)

        if isinstance(node, ast.IfExp):
            cond = self.evaluate(node.test)
            self._require_bool(cond, "conditional test")
            return self.evaluate(node.body if cond else node.orelse)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    _expression_error(
                        self.location,
                        "unsupported function call target",
                        "use approved function names only",
                    )
                )
            fn_name = node.func.id
            if fn_name == "col":
                arg = node.args[0]
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                    raise ValueError(
                        _expression_error(
                            self.location,
                            "function 'col' requires a string literal argument",
                            "use col(\"column_name\")",
                        )
                    )
                col_name = arg.value
                if col_name not in self.row:
                    raise ValueError(
                        _expression_error(
                            self.location,
                            f"column '{col_name}' was not found for col(...)",
                            "use an existing source column name and include it in depends_on",
                        )
                    )
                return self.row[col_name]

            args = [self.evaluate(arg) for arg in node.args]
            return self._call_function(fn_name, args)

        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported runtime expression element '{type(node).__name__}'",
                "use approved expression syntax only",
            )
        )

    def _require_bool(self, value: object, context: str) -> bool:
        if not isinstance(value, bool):
            raise ValueError(
                _expression_error(
                    self.location,
                    f"{context} must be boolean but was '{type(value).__name__}'",
                    "use boolean expressions or explicit to_bool(...) conversion",
                )
            )
        return value

    def _require_number(self, value: object, context: str) -> float | int:
        if not _is_number(value):
            raise ValueError(
                _expression_error(
                    self.location,
                    f"{context} must be numeric but was '{type(value).__name__}'",
                    "use numeric operands or explicit to_int/to_decimal conversion",
                )
            )
        return value

    def _eval_binary(self, op: ast.AST, left: object, right: object) -> Any:
        if left is None or right is None:
            raise ValueError(
                _expression_error(
                    self.location,
                    "binary operators do not accept null operands",
                    "use coalesce(...) to provide non-null defaults before arithmetic",
                )
            )
        if isinstance(op, ast.Add):
            if _is_number(left) and _is_number(right):
                return left + right
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            raise ValueError(
                _expression_error(
                    self.location,
                    "operator '+' requires both numeric or both text operands",
                    "use explicit casts or concat(...) for text composition",
                )
            )
        if isinstance(op, ast.Sub):
            return self._require_number(left, "left operand of '-'") - self._require_number(
                right, "right operand of '-'"
            )
        if isinstance(op, ast.Mult):
            return self._require_number(left, "left operand of '*'") * self._require_number(
                right, "right operand of '*'"
            )
        if isinstance(op, ast.Div):
            denom = self._require_number(right, "right operand of '/'")
            if denom == 0:
                raise ValueError(
                    _expression_error(
                        self.location,
                        "division by zero in '/'",
                        "ensure the denominator is non-zero before division",
                    )
                )
            return self._require_number(left, "left operand of '/'") / denom
        if isinstance(op, ast.FloorDiv):
            denom = self._require_number(right, "right operand of '//'")
            if denom == 0:
                raise ValueError(
                    _expression_error(
                        self.location,
                        "division by zero in '//'",
                        "ensure the denominator is non-zero before floor division",
                    )
                )
            return self._require_number(left, "left operand of '//'") // denom
        if isinstance(op, ast.Mod):
            denom = self._require_number(right, "right operand of '%'")
            if denom == 0:
                raise ValueError(
                    _expression_error(
                        self.location,
                        "modulo by zero in '%'",
                        "ensure the modulo denominator is non-zero",
                    )
                )
            return self._require_number(left, "left operand of '%'") % denom
        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported binary operator '{type(op).__name__}'",
                "use +, -, *, /, //, or %",
            )
        )

    def _eval_unary(self, op: ast.AST, value: object) -> Any:
        if isinstance(op, ast.Not):
            return not self._require_bool(value, "operand of 'not'")
        if isinstance(op, ast.UAdd):
            return +self._require_number(value, "operand of unary '+'")
        if isinstance(op, ast.USub):
            return -self._require_number(value, "operand of unary '-'")
        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported unary operator '{type(op).__name__}'",
                "use unary +, -, or not",
            )
        )

    def _eval_bool(self, op: ast.AST, values: list[ast.AST]) -> bool:
        if not values:
            raise ValueError(
                _expression_error(
                    self.location,
                    "boolean operation requires one or more operands",
                    "provide boolean operands for and/or",
                )
            )
        first = self._require_bool(self.evaluate(values[0]), "first boolean operand")
        if isinstance(op, ast.And):
            if not first:
                return False
            for idx, value_node in enumerate(values[1:], start=2):
                current = self._require_bool(self.evaluate(value_node), f"boolean operand {idx}")
                if not current:
                    return False
            return True
        if isinstance(op, ast.Or):
            if first:
                return True
            for idx, value_node in enumerate(values[1:], start=2):
                current = self._require_bool(self.evaluate(value_node), f"boolean operand {idx}")
                if current:
                    return True
            return False
        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported boolean operator '{type(op).__name__}'",
                "use and/or",
            )
        )

    def _eval_compare(self, node: ast.Compare) -> bool:
        left_value = self.evaluate(node.left)
        for op, right_node in zip(node.ops, node.comparators, strict=True):
            right_value = self.evaluate(right_node)
            if not self._compare_values(op, left_value, right_value):
                return False
            left_value = right_value
        return True

    def _compare_values(self, op: ast.AST, left: object, right: object) -> bool:
        if left is None or right is None:
            raise ValueError(
                _expression_error(
                    self.location,
                    "comparisons do not accept null operands",
                    "use is_null(...) or coalesce(...) before comparison",
                )
            )

        same_numeric = _is_number(left) and _is_number(right)
        same_text = isinstance(left, str) and isinstance(right, str)
        same_bool = isinstance(left, bool) and isinstance(right, bool)
        if not (same_numeric or same_text or same_bool):
            raise ValueError(
                _expression_error(
                    self.location,
                    f"cannot compare '{type(left).__name__}' to '{type(right).__name__}'",
                    "compare like types or cast explicitly",
                )
            )

        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported comparison operator '{type(op).__name__}'",
                "use ==, !=, <, <=, >, or >=",
            )
        )

    def _call_function(self, fn_name: str, args: list[object]) -> Any:
        if fn_name == "if_else":
            cond = self._require_bool(args[0], "if_else condition")
            return args[1] if cond else args[2]
        if fn_name == "coalesce":
            for value in args:
                if value is not None:
                    return value
            return None
        if fn_name == "abs":
            return abs(self._require_number(args[0], "abs argument"))
        if fn_name == "round":
            value = self._require_number(args[0], "round value")
            if len(args) == 1:
                return round(value)
            ndigits = args[1]
            if isinstance(ndigits, bool) or not isinstance(ndigits, int):
                raise ValueError(
                    _expression_error(
                        self.location,
                        "round ndigits must be an integer",
                        "set the second round argument to an integer value",
                    )
                )
            return round(value, ndigits)
        if fn_name == "min":
            return self._minmax(args, fn_name="min")
        if fn_name == "max":
            return self._minmax(args, fn_name="max")
        if fn_name == "concat":
            parts: list[str] = []
            for idx, value in enumerate(args, start=1):
                if value is None:
                    raise ValueError(
                        _expression_error(
                            self.location,
                            f"concat argument {idx} is null",
                            "use coalesce(...) to provide non-null text values",
                        )
                    )
                if isinstance(value, (dict, list, tuple, set, bytes)):
                    raise ValueError(
                        _expression_error(
                            self.location,
                            f"concat argument {idx} has unsupported type '{type(value).__name__}'",
                            "use scalar values only in concat(...)",
                        )
                    )
                parts.append(str(value))
            return "".join(parts)
        if fn_name == "is_null":
            return args[0] is None
        if fn_name == "to_int":
            return self._to_int(args[0])
        if fn_name == "to_decimal":
            return self._to_decimal(args[0])
        if fn_name == "to_text":
            return self._to_text(args[0])
        if fn_name == "to_bool":
            return self._to_bool(args[0])
        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported function '{fn_name}'",
                "use approved derived expression DSL functions only",
            )
        )

    def _minmax(self, args: list[object], *, fn_name: str) -> Any:
        if any(value is None for value in args):
            raise ValueError(
                _expression_error(
                    self.location,
                    f"{fn_name}(...) does not accept null arguments",
                    "use coalesce(...) before calling min/max",
                )
            )
        if all(_is_number(value) for value in args):
            return min(args) if fn_name == "min" else max(args)
        if all(isinstance(value, str) for value in args):
            return min(args) if fn_name == "min" else max(args)
        raise ValueError(
            _expression_error(
                self.location,
                f"{fn_name}(...) requires all arguments to be numeric or all text",
                "cast values explicitly so argument types are consistent",
            )
        )

    def _to_int(self, value: object) -> int:
        if isinstance(value, bool):
            raise ValueError(
                _expression_error(
                    self.location,
                    "to_int(...) does not accept boolean values",
                    "cast from numeric/text values, or use to_bool(...) for boolean conversion",
                )
            )
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"to_int(...) cannot convert non-integer float '{value}'",
                        "use round(...) first or provide an integer-like value",
                    )
                )
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text == "":
                raise ValueError(
                    _expression_error(
                        self.location,
                        "to_int(...) cannot convert an empty string",
                        "provide a string containing an integer value",
                    )
                )
            try:
                return int(text)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"to_int(...) could not parse '{value}'",
                        "provide an integer-like string such as '42'",
                    )
                ) from exc
        raise ValueError(
            _expression_error(
                self.location,
                f"to_int(...) cannot convert type '{type(value).__name__}'",
                "provide a numeric or integer-like text value",
            )
        )

    def _to_decimal(self, value: object) -> float:
        if isinstance(value, bool):
            raise ValueError(
                _expression_error(
                    self.location,
                    "to_decimal(...) does not accept boolean values",
                    "provide a numeric/text value instead",
                )
            )
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if text == "":
                raise ValueError(
                    _expression_error(
                        self.location,
                        "to_decimal(...) cannot convert an empty string",
                        "provide a string containing a numeric value",
                    )
                )
            try:
                return float(text)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"to_decimal(...) could not parse '{value}'",
                        "provide a numeric string such as '10.5'",
                    )
                ) from exc
        raise ValueError(
            _expression_error(
                self.location,
                f"to_decimal(...) cannot convert type '{type(value).__name__}'",
                "provide a numeric or numeric-like text value",
            )
        )

    def _to_text(self, value: object) -> str:
        if value is None:
            raise ValueError(
                _expression_error(
                    self.location,
                    "to_text(...) does not accept null values",
                    "use coalesce(...) to provide a non-null default first",
                )
            )
        if isinstance(value, (dict, list, tuple, set, bytes)):
            raise ValueError(
                _expression_error(
                    self.location,
                    f"to_text(...) cannot convert type '{type(value).__name__}'",
                    "use scalar values only",
                )
            )
        return str(value)

    def _to_bool(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            if value in {0, 1}:
                return bool(value)
            raise ValueError(
                _expression_error(
                    self.location,
                    f"to_bool(...) integer '{value}' is not valid",
                    "use 0/1 integer values for boolean conversion",
                )
            )
        if isinstance(value, float):
            if value in {0.0, 1.0}:
                return bool(int(value))
            raise ValueError(
                _expression_error(
                    self.location,
                    f"to_bool(...) float '{value}' is not valid",
                    "use 0.0/1.0 values for boolean conversion",
                )
            )
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
            raise ValueError(
                _expression_error(
                    self.location,
                    f"to_bool(...) could not parse '{value}'",
                    "use one of: true, false, 1, 0, yes, no",
                )
            )
        raise ValueError(
            _expression_error(
                self.location,
                f"to_bool(...) cannot convert type '{type(value).__name__}'",
                "provide a bool, 0/1 numeric value, or parseable boolean text",
            )
        )

