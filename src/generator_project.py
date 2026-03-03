"""Compatibility shim for generation pipeline APIs.

Canonical implementation now lives under `src.generation`.
"""

from src.generation.pipeline import *
from src.generation.dependency import _dependency_order, dependency_order

__all__ = [name for name in globals() if not name.startswith("__")]
