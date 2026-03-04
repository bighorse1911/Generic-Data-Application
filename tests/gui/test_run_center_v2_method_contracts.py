import unittest

import src.gui.v2.routes.run_center_impl as run_center_module
from src.gui.v2.routes import run_center_io
from src.gui.v2.routes import run_center_nav
from src.gui.v2.routes import run_center_runs
from src.gui.v2.routes.run_center_impl import RunCenterV2Screen


class TestRunCenterV2MethodContracts(unittest.TestCase):
    def test_extracted_modules_export_expected_methods(self) -> None:
        nav_expected = (
            "on_show",
            "on_hide",
            "_register_focus_anchors",
            "_register_shortcuts",
            "_focus_next_anchor",
            "_focus_previous_anchor",
            "_cancel_if_running",
            "_show_shortcuts_help",
            "_show_notifications_history",
            "_notify",
            "_set_inspector_for_config",
            "_set_focus",
        )
        io_expected = (
            "_sync_viewmodel_from_vars",
            "_browse_schema_path",
            "_load_schema",
            "_ensure_project",
            "_save_profile",
            "_load_profile",
        )
        run_expected = (
            "_clear_tree",
            "_set_running",
            "_cancel_run",
            "_is_cancel_requested",
            "_append_history",
            "_on_runtime_event",
            "_on_multiprocess_event",
            "_on_run_failed",
            "_on_run_cancelled",
            "_run_estimate",
            "_run_build_plan",
            "_start_benchmark",
            "_start_generation",
        )

        for name in nav_expected:
            self.assertTrue(hasattr(run_center_nav, name), f"Missing run-center nav method: {name}")
        for name in io_expected:
            self.assertTrue(hasattr(run_center_io, name), f"Missing run-center IO method: {name}")
        for name in run_expected:
            self.assertTrue(hasattr(run_center_runs, name), f"Missing run-center run method: {name}")

    def test_screen_wrappers_delegate_to_extracted_modules(self) -> None:
        wrapper_to_delegate = {
            "on_show": ("run_center_nav", run_center_nav.on_show),
            "on_hide": ("run_center_nav", run_center_nav.on_hide),
            "_register_focus_anchors": ("run_center_nav", run_center_nav._register_focus_anchors),
            "_register_shortcuts": ("run_center_nav", run_center_nav._register_shortcuts),
            "_focus_next_anchor": ("run_center_nav", run_center_nav._focus_next_anchor),
            "_focus_previous_anchor": ("run_center_nav", run_center_nav._focus_previous_anchor),
            "_cancel_if_running": ("run_center_nav", run_center_nav._cancel_if_running),
            "_show_shortcuts_help": ("run_center_nav", run_center_nav._show_shortcuts_help),
            "_show_notifications_history": (
                "run_center_nav",
                run_center_nav._show_notifications_history,
            ),
            "_notify": ("run_center_nav", run_center_nav._notify),
            "_set_inspector_for_config": ("run_center_nav", run_center_nav._set_inspector_for_config),
            "_set_focus": ("run_center_nav", run_center_nav._set_focus),
            "_sync_viewmodel_from_vars": ("run_center_io", run_center_io._sync_viewmodel_from_vars),
            "_browse_schema_path": ("run_center_io", run_center_io._browse_schema_path),
            "_load_schema": ("run_center_io", run_center_io._load_schema),
            "_ensure_project": ("run_center_io", run_center_io._ensure_project),
            "_save_profile": ("run_center_io", run_center_io._save_profile),
            "_load_profile": ("run_center_io", run_center_io._load_profile),
            "_clear_tree": ("run_center_runs", run_center_runs._clear_tree),
            "_set_running": ("run_center_runs", run_center_runs._set_running),
            "_cancel_run": ("run_center_runs", run_center_runs._cancel_run),
            "_is_cancel_requested": ("run_center_runs", run_center_runs._is_cancel_requested),
            "_append_history": ("run_center_runs", run_center_runs._append_history),
            "_on_runtime_event": ("run_center_runs", run_center_runs._on_runtime_event),
            "_on_multiprocess_event": ("run_center_runs", run_center_runs._on_multiprocess_event),
            "_on_run_failed": ("run_center_runs", run_center_runs._on_run_failed),
            "_on_run_cancelled": ("run_center_runs", run_center_runs._on_run_cancelled),
            "_run_estimate": ("run_center_runs", run_center_runs._run_estimate),
            "_run_build_plan": ("run_center_runs", run_center_runs._run_build_plan),
            "_start_benchmark": ("run_center_runs", run_center_runs._start_benchmark),
            "_start_generation": ("run_center_runs", run_center_runs._start_generation),
        }

        for wrapper_name, (module_name, delegate) in wrapper_to_delegate.items():
            wrapper = RunCenterV2Screen.__dict__[wrapper_name]
            self.assertIn(module_name, wrapper.__code__.co_names)
            self.assertIn(delegate.__name__, wrapper.__code__.co_names)

    def test_new_modules_are_imported_on_facade_module(self) -> None:
        self.assertTrue(hasattr(run_center_module, "run_center_nav"))
        self.assertTrue(hasattr(run_center_module, "run_center_io"))
        self.assertTrue(hasattr(run_center_module, "run_center_runs"))


if __name__ == "__main__":
    unittest.main()
