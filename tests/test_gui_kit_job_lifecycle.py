import unittest

from src.gui_kit.job_lifecycle import JobLifecycleController


class TestJobLifecycleController(unittest.TestCase):
    def test_run_async_success_with_success_phase(self):
        set_running_calls: list[tuple[bool, str]] = []
        done_calls: list[int] = []
        failed_calls: list[str] = []

        def run_async(worker, on_done, on_failed):
            try:
                on_done(worker())
            except Exception as exc:  # pragma: no cover
                on_failed(exc)

        controller = JobLifecycleController(
            set_running=lambda running, phase: set_running_calls.append((running, phase)),
            run_async=run_async,
        )

        started = controller.run_async(
            worker=lambda: 3,
            on_done=lambda payload: done_calls.append(int(payload)),
            on_failed=lambda message: failed_calls.append(message),
            phase_label="Generating data for all tables...",
            success_phase="Generation complete.",
        )

        self.assertTrue(started)
        self.assertEqual(done_calls, [3])
        self.assertEqual(failed_calls, [])
        self.assertEqual(
            set_running_calls,
            [
                (True, "Generating data for all tables..."),
                (False, "Generation complete."),
            ],
        )
        self.assertFalse(controller.state.is_running)

    def test_run_async_failure_sets_last_error_and_failure_phase(self):
        set_running_calls: list[tuple[bool, str]] = []
        failed_calls: list[str] = []

        def run_async(worker, on_done, on_failed):
            try:
                on_done(worker())
            except Exception as exc:
                on_failed(exc)

        controller = JobLifecycleController(
            set_running=lambda running, phase: set_running_calls.append((running, phase)),
            run_async=run_async,
        )

        started = controller.run_async(
            worker=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            on_done=lambda _payload: None,
            on_failed=lambda message: failed_calls.append(message),
            phase_label="Creating tables and inserting rows into SQLite...",
            failure_phase="Failed.",
        )

        self.assertTrue(started)
        self.assertEqual(failed_calls, ["boom"])
        self.assertEqual(controller.state.last_error, "boom")
        self.assertEqual(
            set_running_calls,
            [
                (True, "Creating tables and inserting rows into SQLite..."),
                (False, "Failed."),
            ],
        )
        self.assertFalse(controller.state.is_running)

    def test_run_async_rejects_while_running(self):
        run_async_invocations = {"value": 0}

        def run_async(_worker, _on_done, _on_failed):
            run_async_invocations["value"] += 1

        controller = JobLifecycleController(
            set_running=lambda _running, _phase: None,
            run_async=run_async,
        )
        controller.state.is_running = True

        started = controller.run_async(
            worker=lambda: 1,
            on_done=lambda _payload: None,
            on_failed=lambda _message: None,
            phase_label="Generating sample data (10 rows per root table)...",
        )

        self.assertFalse(started)
        self.assertEqual(run_async_invocations["value"], 0)


if __name__ == "__main__":
    unittest.main()
