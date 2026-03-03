from __future__ import annotations

class _BackToRouteAdapter:
    """Adapter so shared tool frames can call app.go_home() to a target route."""

    def __init__(self, navigate) -> None:
        self._navigate = navigate

    def go_home(self) -> None:
        self._navigate()



__all__ = ["_BackToRouteAdapter"]
