from __future__ import annotations

from typing import Any, Dict

from src.derived_expression import CompiledDerivedExpression


_ORDERED_CHOICE_STATE: Dict[tuple[str, str], Dict[str, Any]] = {}
_STATE_TRANSITION_CONFIG_STATE: Dict[tuple[str, str], Dict[str, Any]] = {}
_STATE_TRANSITION_ENTITY_STATE: Dict[tuple[str, str, tuple[str, str]], Dict[str, Any]] = {}
_DERIVED_EXPRESSION_STATE: Dict[tuple[str, str], CompiledDerivedExpression] = {}


def reset_runtime_generator_state() -> None:
    _ORDERED_CHOICE_STATE.clear()
    _STATE_TRANSITION_CONFIG_STATE.clear()
    _STATE_TRANSITION_ENTITY_STATE.clear()
    _DERIVED_EXPRESSION_STATE.clear()
