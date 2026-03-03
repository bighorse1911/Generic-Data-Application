"""Compatibility shim for schema model APIs.

Canonical implementation now lives under `src.schema`.
"""

from src.schema.model_impl import *

__all__ = [name for name in globals() if not name.startswith("__")]
