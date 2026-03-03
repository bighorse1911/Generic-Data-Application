"""Compatibility shim for schema editor base screen modules.

Canonical implementation now lives under `src.gui.schema.editor_base`.
"""

from src.gui.schema.editor_base import *

__all__ = [name for name in globals() if not name.startswith("__")]
