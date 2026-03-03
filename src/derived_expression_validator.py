from __future__ import annotations

import ast

from src.derived_expression_common import _expression_error, _is_scalar_literal
from src.derived_expression_types import MAX_EXPRESSION_DEPTH


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

