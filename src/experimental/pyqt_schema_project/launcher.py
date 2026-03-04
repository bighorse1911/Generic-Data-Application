from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping, Sequence

EXPERIMENT_ENV_VAR = "GDA_ENABLE_PYQT_EXPERIMENT"
_PYQT_MODULE = "PyQt6"
_LAUNCH_MODULE = "src.experimental.pyqt_schema_project.main"


def _error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _env_value(value: object) -> str:
    return str(value).strip().lower()


def is_experiment_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    raw = _env_value(source.get(EXPERIMENT_ENV_VAR, ""))
    return raw in {"1", "true", "yes", "on"}


def check_pyqt6_available() -> tuple[bool, str | None]:
    try:
        spec = importlib.util.find_spec(_PYQT_MODULE)
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            _error(
                "PyQt experiment launcher",
                f"failed to inspect optional dependency '{_PYQT_MODULE}' ({exc})",
                "install PyQt6 or disable the experiment by unsetting GDA_ENABLE_PYQT_EXPERIMENT",
            ),
        )
    if spec is None:
        return (
            False,
            _error(
                "PyQt experiment launcher",
                "optional dependency 'PyQt6' is not installed",
                "install PyQt6 for the experiment or unset GDA_ENABLE_PYQT_EXPERIMENT",
            ),
        )
    return True, None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _merged_env(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    merged = dict(os.environ)
    if overrides:
        merged.update({str(k): str(v) for k, v in overrides.items()})
    return merged


def launch_pyqt_schema_project(
    *,
    env: Mapping[str, str] | None = None,
    schema_path: str | None = None,
    cwd: str | Path | None = None,
    python_executable: str | None = None,
    spawn: Callable[..., object] | None = None,
) -> tuple[bool, str]:
    if not is_experiment_enabled(env):
        return (
            False,
            _error(
                "PyQt experiment launcher",
                "experiment is disabled",
                "set GDA_ENABLE_PYQT_EXPERIMENT=1 before opening Home v2",
            ),
        )

    available, message = check_pyqt6_available()
    if not available:
        assert message is not None
        return False, message

    command: list[str] = [python_executable or sys.executable, "-m", _LAUNCH_MODULE]
    if schema_path:
        command.extend(["--schema", schema_path])

    target_cwd = Path(cwd) if cwd is not None else _repo_root()
    process_env = _merged_env(env)
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    spawner = spawn or subprocess.Popen

    try:
        spawner(
            command,
            cwd=os.fspath(target_cwd),
            env=process_env,
            creationflags=creationflags,
        )
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            _error(
                "PyQt experiment launcher",
                f"failed to start process ({exc})",
                "verify Python executable, working directory, and PyQt6 installation",
            ),
        )

    return (
        True,
        "PyQt experiment launcher: started optional PyQt schema project window. "
        "Fix: if no window appears, verify PyQt6 and process permissions.",
    )


def build_launch_command(
    *,
    schema_path: str | None = None,
    python_executable: str | None = None,
) -> Sequence[str]:
    command: list[str] = [python_executable or sys.executable, "-m", _LAUNCH_MODULE]
    if schema_path:
        command.extend(["--schema", schema_path])
    return tuple(command)


__all__ = [
    "EXPERIMENT_ENV_VAR",
    "is_experiment_enabled",
    "check_pyqt6_available",
    "launch_pyqt_schema_project",
    "build_launch_command",
]
