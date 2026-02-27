from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

MAX_EXPRESSION_LENGTH = 1000
MAX_EXPRESSION_NODES = 256
MAX_EXPRESSION_DEPTH = 32


def _expression_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _is_scalar_literal(value: object) -> bool:
    return isinstance(value, (int, float, str, bool)) or value is None


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class CompiledDerivedExpression:
    expression: str
    body: ast.AST
    references: tuple[str, ...]


class _ExpressionValidator:
    _ALLOWED_BINARY_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
    _ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub, ast.Not)
    _ALLOWED_BOOL_OPS = (ast.And, ast.Or)
    _ALLOWED_COMPARE_OPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)

    _FUNCTION_ARITY: dict[str, tuple[int, int | None]] = {
        "if_else": (3, 3),
        "coalesce": (1, None),
        "abs": (1, 1),
        "round": (1, 2),
        "min": (1, None),
        "max": (1, None),
        "concat": (1, None),
        "is_null": (1, 1),
        "to_int": (1, 1),
        "to_decimal": (1, 1),
        "to_text": (1, 1),
        "to_bool": (1, 1),
        "col": (1, 1),
    }

    def __init__(self, *, location: str) -> None:
        self.location = location
        self.references: set[str] = set()

    def validate(self, node: ast.AST, *, depth: int) -> None:
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError(
                _expression_error(
                    self.location,
                    f"expression nesting exceeds {MAX_EXPRESSION_DEPTH} levels",
                    "simplify the formula into smaller expressions",
                )
            )

        if isinstance(node, ast.Constant):
            if not _is_scalar_literal(node.value):
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"unsupported literal type '{type(node.value).__name__}'",
                        "use scalar literals only (number/text/bool/null)",
                    )
                )
            return

        if isinstance(node, ast.Name):
            if not isinstance(node.ctx, ast.Load):
                raise ValueError(
                    _expression_error(
                        self.location,
                        "expression references must be read-only",
                        "use column names as read-only values",
                    )
                )
            self.references.add(node.id)
            return

        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, self._ALLOWED_BINARY_OPS):
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"binary operator '{type(node.op).__name__}' is not allowed",
                        "use +, -, *, /, //, or %",
                    )
                )
            self.validate(node.left, depth=depth + 1)
            self.validate(node.right, depth=depth + 1)
            return

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, self._ALLOWED_UNARY_OPS):
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"unary operator '{type(node.op).__name__}' is not allowed",
                        "use unary +, -, or not",
                    )
                )
            self.validate(node.operand, depth=depth + 1)
            return

        if isinstance(node, ast.BoolOp):
            if not isinstance(node.op, self._ALLOWED_BOOL_OPS):
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"boolean operator '{type(node.op).__name__}' is not allowed",
                        "use and/or boolean operators",
                    )
                )
            if len(node.values) < 2:
                raise ValueError(
                    _expression_error(
                        self.location,
                        "boolean expression must include two or more operands",
                        "provide both left and right boolean operands",
                    )
                )
            for value in node.values:
                self.validate(value, depth=depth + 1)
            return

        if isinstance(node, ast.Compare):
            self.validate(node.left, depth=depth + 1)
            for op in node.ops:
                if not isinstance(op, self._ALLOWED_COMPARE_OPS):
                    raise ValueError(
                        _expression_error(
                            self.location,
                            f"comparison operator '{type(op).__name__}' is not allowed",
                            "use ==, !=, <, <=, >, or >=",
                        )
                    )
            for comparator in node.comparators:
                self.validate(comparator, depth=depth + 1)
            return

        if isinstance(node, ast.IfExp):
            self.validate(node.test, depth=depth + 1)
            self.validate(node.body, depth=depth + 1)
            self.validate(node.orelse, depth=depth + 1)
            return

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    _expression_error(
                        self.location,
                        "function calls must use simple function names",
                        "call only approved DSL functions directly",
                    )
                )
            func_name = node.func.id
            arity = self._FUNCTION_ARITY.get(func_name)
            if arity is None:
                allowed = ", ".join(sorted(self._FUNCTION_ARITY.keys()))
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"function '{func_name}' is not allowed",
                        f"use one of: {allowed}",
                    )
                )
            if node.keywords:
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"function '{func_name}' does not support keyword arguments",
                        "use positional arguments only",
                    )
                )
            min_args, max_args = arity
            arg_count = len(node.args)
            if arg_count < min_args:
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"function '{func_name}' requires at least {min_args} argument(s)",
                        "provide the required positional arguments",
                    )
                )
            if max_args is not None and arg_count > max_args:
                raise ValueError(
                    _expression_error(
                        self.location,
                        f"function '{func_name}' accepts at most {max_args} argument(s)",
                        "remove extra function arguments",
                    )
                )

            if func_name == "col":
                arg_node = node.args[0]
                if not isinstance(arg_node, ast.Constant) or not isinstance(arg_node.value, str):
                    raise ValueError(
                        _expression_error(
                            self.location,
                            "function 'col' requires a string literal column name",
                            "use col(\"column_name\") with a quoted column name",
                        )
                    )
                col_name = arg_node.value
                if col_name.strip() == "":
                    raise ValueError(
                        _expression_error(
                            self.location,
                            "function 'col' column name cannot be empty",
                            "provide a non-empty column name in col(...)",
                        )
                    )
                self.references.add(col_name)
                return

            for arg in node.args:
                self.validate(arg, depth=depth + 1)
            return

        raise ValueError(
            _expression_error(
                self.location,
                f"unsupported expression element '{type(node).__name__}'",
                "use literals, column refs, allowed operators, conditionals, and approved functions only",
            )
        )


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


def compile_derived_expression(
    expression: str,
    *,
    location: str,
) -> CompiledDerivedExpression:
    if not isinstance(expression, str) or expression.strip() == "":
        raise ValueError(
            _expression_error(
                location,
                "params.expression is required",
                "set params.expression to a non-empty expression string",
            )
        )
    trimmed = expression.strip()
    if len(trimmed) > MAX_EXPRESSION_LENGTH:
        raise ValueError(
            _expression_error(
                location,
                f"expression length exceeds {MAX_EXPRESSION_LENGTH} characters",
                "shorten the expression or split logic across multiple derived columns",
            )
        )

    try:
        parsed = ast.parse(trimmed, mode="eval")
    except SyntaxError as exc:
        detail = f"line {exc.lineno}, column {exc.offset}" if exc.lineno and exc.offset else "syntax error"
        raise ValueError(
            _expression_error(
                location,
                f"expression syntax is invalid ({detail})",
                "use a valid expression with allowed operators/functions",
            )
        ) from exc

    node_count = sum(1 for _ in ast.walk(parsed))
    if node_count > MAX_EXPRESSION_NODES:
        raise ValueError(
            _expression_error(
                location,
                f"expression complexity exceeds {MAX_EXPRESSION_NODES} AST nodes",
                "simplify the expression into smaller steps",
            )
        )

    validator = _ExpressionValidator(location=location)
    validator.validate(parsed.body, depth=1)

    return CompiledDerivedExpression(
        expression=trimmed,
        body=parsed.body,
        references=tuple(sorted(validator.references)),
    )


def extract_derived_expression_references(
    expression: str,
    *,
    location: str,
) -> tuple[str, ...]:
    compiled = compile_derived_expression(expression, location=location)
    return compiled.references


def evaluate_derived_expression(
    compiled: CompiledDerivedExpression,
    *,
    row: Mapping[str, Any],
    location: str,
) -> Any:
    evaluator = _ExpressionEvaluator(row=row, location=location)
    return evaluator.evaluate(compiled.body)


def is_iso_date_text(value: object) -> bool:
    if not isinstance(value, str) or value.strip() == "":
        return False
    try:
        date.fromisoformat(value.strip())
    except Exception:
        return False
    return True


def is_iso_datetime_text(value: object) -> bool:
    if not isinstance(value, str) or value.strip() == "":
        return False
    text = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(text)
    except Exception:
        return False
    return True
