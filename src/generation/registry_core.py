from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class GenContext:
    """Row-level context so generators can correlate."""

    row_index: int
    table: str
    row: Dict[str, Any]
    rng: random.Random
    column: str = ""
    dtype: str = ""


GeneratorFn = Callable[[Dict[str, Any], GenContext], Any]

REGISTRY: Dict[str, GeneratorFn] = {}


def register(name: str):
    def deco(fn: GeneratorFn) -> GeneratorFn:
        if name in REGISTRY:
            raise KeyError(
                f"Generator '{name}' is already registered. Existing: {sorted(REGISTRY.keys())}"
            )
        REGISTRY[name] = fn
        return fn

    return deco


def get_generator(name: str) -> GeneratorFn:
    if name not in REGISTRY:
        raise KeyError(f"Unknown generator '{name}'. Registered: {sorted(REGISTRY.keys())}")
    return REGISTRY[name]
