import time
import tkinter as tk
import unittest

from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.ui_dispatch import UIDispatcher
from src.multiprocessing_runtime import MultiprocessEvent
from src.performance_scaling import RuntimeEvent


class _Widget:
    def __init__(self) -> None:
        self.state = "normal"

    def configure(self, **kwargs) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class _CancelError(RuntimeError):
    pass


class TestRunLifecycleController(unittest.TestCase):
    def test_set_running_toggles_controls(self):
        phase = {"value": ""}
        rows = {"value": ""}
        eta = {"value": ""}
        progress = {"value": 0.0}
        status = {"value": ""}

        action_a = _Widget()
        action_b = _Widget()
        cancel = _Widget()

        controller = RunLifecycleController(
            set_phase=lambda text: phase.__setitem__("value", text),
            set_rows=lambda text: rows.__setitem__("value", text),
            set_eta=lambda text: eta.__setitem__("value", text),
            set_progress=lambda value: progress.__setitem__("value", value),
            set_status=lambda text: status.__setitem__("value", text),
            action_buttons=[action_a, action_b],
            cancel_button=cancel,
        )

        controller.set_running(True, "Running")
        self.assertTrue(controller.state.is_running)
        self.assertEqual(phase["value"], "Running")
        self.assertEqual(action_a.state, "disabled")
        self.assertEqual(action_b.state, "disabled")
        self.assertEqual(cancel.state, "normal")

        controller.set_running(False, "Idle")
        self.assertFalse(controller.state.is_running)
        self.assertEqual(action_a.state, "normal")
        self.assertEqual(action_b.state, "normal")
        self.assertEqual(cancel.state, "disabled")

    def test_runtime_event_updates_progress_and_eta(self):
        now = {"value": 100.0}
        rows = {"value": ""}
        eta = {"value": ""}
        progress = {"value": 0.0}

        controller = RunLifecycleController(
            set_phase=lambda _text: None,
            set_rows=lambda text: rows.__setitem__("value", text),
            set_eta=lambda text: eta.__setitem__("value", text),
            set_progress=lambda value: progress.__setitem__("value", value),
            set_status=None,
            action_buttons=[_Widget()],
            cancel_button=_Widget(),
            time_fn=lambda: now["value"],
        )

        controller.set_running(True, "Starting")
        now["value"] = 105.0
        controller.handle_runtime_event(
            RuntimeEvent(kind="progress", rows_processed=50, total_rows=100, message="Running")
        )
        self.assertEqual(progress["value"], 50.0)
        self.assertIn("Rows processed: 50/100", rows["value"])
        self.assertIn("ETA: 5s", eta["value"])

        now["value"] = 110.0
        controller.handle_runtime_event(RuntimeEvent(kind="run_done", rows_processed=100, total_rows=100))
        self.assertEqual(progress["value"], 100.0)
        self.assertIn("Completed in", eta["value"])

    def test_multiprocess_fallback_retry_and_cancel(self):
        phase = {"value": ""}
        eta = {"value": ""}
        status = {"value": ""}

        controller = RunLifecycleController(
            set_phase=lambda text: phase.__setitem__("value", text),
            set_rows=lambda _text: None,
            set_eta=lambda text: eta.__setitem__("value", text),
            set_progress=lambda _value: None,
            set_status=lambda text: status.__setitem__("value", text),
            action_buttons=[_Widget()],
            cancel_button=_Widget(),
        )

        controller.set_running(True, "Running")
        controller.handle_multiprocess_event(MultiprocessEvent(kind="fallback", message="Switching"))
        self.assertEqual(phase["value"], "Switching")
        self.assertEqual(eta["value"], "ETA: fallback")
        self.assertTrue(controller.state.fallback_used)

        controller.handle_multiprocess_event(MultiprocessEvent(kind="partition_failed", retry_count=2))
        self.assertEqual(controller.state.last_retry_count, 2)

        controller.request_cancel("Cancelling now")
        self.assertTrue(controller.state.cancel_requested)
        self.assertEqual(phase["value"], "Cancelling...")
        self.assertEqual(status["value"], "Cancelling now")

    def test_transition_helpers_set_phase_and_status(self):
        phase = {"value": ""}
        status = {"value": ""}

        controller = RunLifecycleController(
            set_phase=lambda text: phase.__setitem__("value", text),
            set_rows=lambda _text: None,
            set_eta=lambda _text: None,
            set_progress=lambda _value: None,
            set_status=lambda text: status.__setitem__("value", text),
            action_buttons=[_Widget()],
            cancel_button=_Widget(),
        )

        controller.set_running(True, "Working")
        controller.transition_failed("boom", phase="Failed")
        self.assertFalse(controller.state.is_running)
        self.assertEqual(phase["value"], "Failed")
        self.assertEqual(status["value"], "boom")

        controller.set_running(True, "Working")
        controller.transition_cancelled("cancelled by user", phase="Cancelled")
        self.assertFalse(controller.state.is_running)
        self.assertEqual(phase["value"], "Cancelled")
        self.assertEqual(status["value"], "cancelled by user")

    def test_run_async_drops_terminal_callback_when_dispatch_fails(self):
        controller = RunLifecycleController(
            set_phase=lambda _text: None,
            set_rows=lambda _text: None,
            set_eta=lambda _text: None,
            set_progress=lambda _value: None,
            set_status=None,
            action_buttons=[_Widget()],
            cancel_button=_Widget(),
        )

        def bad_after(_ms: int, _callback):
            raise tk.TclError("widget destroyed")

        dispatcher = UIDispatcher(after=bad_after, is_alive=lambda: True)
        calls: list[str] = []

        controller.run_async(
            after=bad_after,
            worker=lambda: 5,
            on_done=lambda value: calls.append(f"done:{value}"),
            on_failed=lambda message: calls.append(f"failed:{message}"),
            on_cancelled=lambda message: calls.append(f"cancel:{message}"),
            phase_label="Working",
            cancel_exceptions=(_CancelError,),
            dispatcher=dispatcher,
        )

        for _ in range(50):
            if not controller.state.is_running:
                break
            time.sleep(0.01)

        self.assertFalse(controller.state.is_running)
        self.assertEqual(calls, [])

    def test_run_async_routes_done_cancel_and_failure(self):
        calls: list[str] = []
        controller = RunLifecycleController(
            set_phase=lambda _text: None,
            set_rows=lambda _text: None,
            set_eta=lambda _text: None,
            set_progress=lambda _value: None,
            set_status=None,
            action_buttons=[_Widget()],
            cancel_button=_Widget(),
        )

        def after(_ms: int, callback):
            callback()
            return None

        def wait_until_idle() -> None:
            for _ in range(50):
                if not controller.state.is_running:
                    return
                time.sleep(0.01)

        controller.run_async(
            after=after,
            worker=lambda: 7,
            on_done=lambda value: (calls.append(f"done:{value}"), controller.transition_complete("Done")),
            on_failed=lambda message: (calls.append(f"failed:{message}"), controller.transition_failed(message)),
            on_cancelled=lambda message: (calls.append(f"cancel:{message}"), controller.transition_cancelled(message)),
            phase_label="Working",
            cancel_exceptions=(_CancelError,),
        )
        wait_until_idle()

        controller.run_async(
            after=after,
            worker=lambda: (_ for _ in ()).throw(_CancelError("cancelled")),
            on_done=lambda value: (calls.append(f"done:{value}"), controller.transition_complete("Done")),
            on_failed=lambda message: (calls.append(f"failed:{message}"), controller.transition_failed(message)),
            on_cancelled=lambda message: (calls.append(f"cancel:{message}"), controller.transition_cancelled(message)),
            phase_label="Working",
            cancel_exceptions=(_CancelError,),
        )
        wait_until_idle()

        controller.run_async(
            after=after,
            worker=lambda: (_ for _ in ()).throw(ValueError("boom")),
            on_done=lambda value: (calls.append(f"done:{value}"), controller.transition_complete("Done")),
            on_failed=lambda message: (calls.append(f"failed:{message}"), controller.transition_failed(message)),
            on_cancelled=lambda message: (calls.append(f"cancel:{message}"), controller.transition_cancelled(message)),
            phase_label="Working",
            cancel_exceptions=(_CancelError,),
        )
        wait_until_idle()

        self.assertIn("done:7", calls)
        self.assertIn("cancel:cancelled", calls)
        self.assertIn("failed:boom", calls)


if __name__ == "__main__":
    unittest.main()
