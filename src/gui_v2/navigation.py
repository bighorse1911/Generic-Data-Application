from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RouteGuardResult:
    allowed: bool
    reason: str


class DirtyRouteGuard:
    """Thin adapter for dirty-state prompts across v2 route transitions."""

    def can_navigate(
        self,
        *,
        dirty_screen: object | None,
        action_name: str,
    ) -> RouteGuardResult:
        if dirty_screen is None:
            return RouteGuardResult(True, "no_dirty_screen")

        confirm_cb = getattr(dirty_screen, "confirm_discard_or_save", None)
        if not callable(confirm_cb):
            return RouteGuardResult(True, "no_guard_callback")

        is_dirty = bool(getattr(dirty_screen, "is_dirty", False))
        if not is_dirty:
            return RouteGuardResult(True, "clean")

        try:
            allowed = bool(confirm_cb(action_name=action_name))
        except Exception:
            return RouteGuardResult(False, "guard_error")
        if not allowed:
            return RouteGuardResult(False, "user_cancelled")
        return RouteGuardResult(True, "confirmed")


def guarded_navigation(
    *,
    guard: DirtyRouteGuard,
    dirty_screen: object | None,
    action_name: str,
    navigate: Callable[[], None],
) -> RouteGuardResult:
    result = guard.can_navigate(dirty_screen=dirty_screen, action_name=action_name)
    if result.allowed:
        navigate()
    return result

