"""Compatibility shim for classic schema GUI screen modules.

Canonical implementation now lives under ``src.gui.schema.classic_screen``.
"""

from src.gui.schema import classic_screen as _classic_screen

_exported_names = [name for name in dir(_classic_screen) if not name.startswith("__")]
for _name in _exported_names:
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_classic_screen, _name)

del _name

__all__ = list(_exported_names)
