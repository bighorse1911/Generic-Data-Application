import os
from pathlib import Path
import unittest
from unittest import mock

from src.experimental.pyqt_schema_project import launcher


class TestPyQtSchemaLauncher(unittest.TestCase):
    def test_is_experiment_enabled_defaults_false(self) -> None:
        self.assertFalse(launcher.is_experiment_enabled(env={}))
        self.assertFalse(launcher.is_experiment_enabled(env={launcher.EXPERIMENT_ENV_VAR: "0"}))

    def test_is_experiment_enabled_truthy_values(self) -> None:
        self.assertTrue(launcher.is_experiment_enabled(env={launcher.EXPERIMENT_ENV_VAR: "1"}))
        self.assertTrue(launcher.is_experiment_enabled(env={launcher.EXPERIMENT_ENV_VAR: "true"}))
        self.assertTrue(launcher.is_experiment_enabled(env={launcher.EXPERIMENT_ENV_VAR: "YES"}))

    def test_check_pyqt6_available_reports_missing_dependency(self) -> None:
        with mock.patch("importlib.util.find_spec", return_value=None):
            ok, message = launcher.check_pyqt6_available()
        self.assertFalse(ok)
        self.assertIsNotNone(message)
        self.assertIn("PyQt experiment launcher", message or "")
        self.assertIn("Fix:", message or "")

    def test_build_launch_command_includes_module_and_schema(self) -> None:
        cmd = launcher.build_launch_command(schema_path="sample.json", python_executable="pythonx")
        self.assertEqual(cmd[0], "pythonx")
        self.assertEqual(cmd[1:3], ("-m", "src.experimental.pyqt_schema_project.main"))
        self.assertEqual(cmd[3:], ("--schema", "sample.json"))

    def test_launch_returns_error_when_env_gate_disabled(self) -> None:
        ok, message = launcher.launch_pyqt_schema_project(env={launcher.EXPERIMENT_ENV_VAR: "0"})
        self.assertFalse(ok)
        self.assertIn("Fix:", message)

    def test_launch_starts_subprocess_when_enabled_and_pyqt_available(self) -> None:
        calls: dict[str, object] = {}

        def _spawn(cmd, **kwargs):  # noqa: ANN001
            calls["cmd"] = list(cmd)
            calls["kwargs"] = dict(kwargs)
            return object()

        with mock.patch.object(launcher, "check_pyqt6_available", return_value=(True, None)):
            ok, message = launcher.launch_pyqt_schema_project(
                env={launcher.EXPERIMENT_ENV_VAR: "1"},
                schema_path="tests/fixtures/default_schema_project.json",
                python_executable="pythonx",
                cwd=Path("."),
                spawn=_spawn,
            )

        self.assertTrue(ok)
        self.assertIn("started", message.lower())
        self.assertEqual(calls["cmd"][0], "pythonx")
        self.assertEqual(calls["cmd"][1:3], ["-m", "src.experimental.pyqt_schema_project.main"])
        self.assertEqual(calls["cmd"][3:], ["--schema", "tests/fixtures/default_schema_project.json"])
        kwargs = calls["kwargs"]
        self.assertIn("cwd", kwargs)
        self.assertIn("env", kwargs)
        self.assertIn(launcher.EXPERIMENT_ENV_VAR, kwargs["env"])


if __name__ == "__main__":
    unittest.main()
