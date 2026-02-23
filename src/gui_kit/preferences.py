"""Workspace preferences persistence helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["WorkspacePreferencesStore", "default_workspace_preferences_path"]

_SCHEMA_VERSION = 1


def default_workspace_preferences_path() -> Path:
    """
    Return the default workspace-preferences path.

    Override with `GDA_WORKSPACE_STATE_PATH` for tests/local diagnostics.
    """

    override = os.getenv("GDA_WORKSPACE_STATE_PATH", "").strip()
    if override:
        return Path(override)
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "GenericDataApplication" / "workspace_state.json"
    return Path.home() / ".generic_data_application" / "workspace_state.json"


class WorkspacePreferencesStore:
    """Versioned JSON store for per-route workspace UI state."""

    def __init__(self, *, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_workspace_preferences_path()
        self._data: dict[str, object] = {
            "schema_version": _SCHEMA_VERSION,
            "routes": {},
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        routes = payload.get("routes")
        if not isinstance(routes, dict):
            routes = {}
        self._data = {
            "schema_version": _SCHEMA_VERSION,
            "routes": routes,
        }

    def get_route_state(self, route_key: str) -> dict[str, object]:
        route = str(route_key).strip()
        routes = self._data.get("routes")
        if route == "" or not isinstance(routes, dict):
            return {}
        payload = routes.get(route)
        if isinstance(payload, dict):
            return dict(payload)
        return {}

    def set_route_state(self, route_key: str, state: dict[str, object]) -> None:
        route = str(route_key).strip()
        if route == "":
            raise ValueError(
                "Workspace preferences: route key is required. "
                "Fix: provide a non-empty route key."
            )
        if not isinstance(state, dict):
            raise ValueError(
                "Workspace preferences: route state must be a dict. "
                "Fix: provide a dict payload for route state."
            )
        routes = self._data.get("routes")
        if not isinstance(routes, dict):
            routes = {}
            self._data["routes"] = routes
        routes[route] = dict(state)

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    def save_route_state(self, route_key: str, state: dict[str, object]) -> bool:
        self.set_route_state(route_key, state)
        return self.save()
