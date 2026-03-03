from __future__ import annotations

import ast
from dataclasses import dataclass


MAX_EXPRESSION_LENGTH = 1000
MAX_EXPRESSION_NODES = 256
MAX_EXPRESSION_DEPTH = 32


@dataclass(frozen=True)
class CompiledDerivedExpression:
    expression: str
    body: ast.AST
    references: tuple[str, ...]


