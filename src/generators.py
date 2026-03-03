"""Compatibility shim for generator registry/built-ins.

Canonical implementation now lives under `src.generation.generator_registry`.
"""

from src.generation.generator_registry import *

__all__ = [name for name in globals() if not name.startswith("__")]
