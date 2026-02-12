from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_repo_path(path_value: str, *, root: Path | None = None) -> Path:
    root_path = root or repo_root()
    raw = Path(path_value.strip())

    if raw.is_absolute():
        if raw.exists():
            return raw
        candidate = _rebuild_from_anchor(raw, root_path, anchor="tests")
        if candidate is not None:
            return candidate
        return raw

    return root_path / raw


def to_repo_relative_path(path_value: str, *, root: Path | None = None) -> str:
    root_path = root or repo_root()
    resolved = resolve_repo_path(path_value, root=root_path)
    try:
        return resolved.relative_to(root_path).as_posix()
    except ValueError:
        return str(resolved)


def _rebuild_from_anchor(raw_path: Path, root_path: Path, *, anchor: str) -> Path | None:
    lowered_parts = [part.lower() for part in raw_path.parts]
    anchor_lower = anchor.lower()
    if anchor_lower not in lowered_parts:
        return None

    idx = lowered_parts.index(anchor_lower)
    return root_path.joinpath(*raw_path.parts[idx:])
