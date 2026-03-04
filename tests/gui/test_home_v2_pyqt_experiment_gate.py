import os
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.experimental.pyqt_schema_project.launcher import EXPERIMENT_ENV_VAR
from src.gui_home import App


class TestHomeV2PyQtExperimentGate(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    @staticmethod
    def _collect_text(widget: tk.Widget, out: list[str]) -> None:
        try:
            text = str(widget.cget("text"))
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            out.append(text)
        for child in widget.winfo_children():
            TestHomeV2PyQtExperimentGate._collect_text(child, out)

    @staticmethod
    def _find_experiment_open_button(home_v2) -> tk.Widget | None:  # noqa: ANN001
        for card in home_v2.cards_frame.winfo_children():
            title = ""
            open_button = None
            for child in card.winfo_children():
                try:
                    text = str(child.cget("text"))
                except Exception:  # noqa: BLE001
                    continue
                if text == "Schema Project PyQt Experiment":
                    title = text
                if text == "Open":
                    open_button = child
            if title and open_button is not None:
                return open_button
        return None

    def test_home_v2_hides_pyqt_experiment_card_when_gate_disabled(self) -> None:
        with mock.patch.dict(os.environ, {EXPERIMENT_ENV_VAR: "0"}, clear=False):
            app = App(self.root, AppConfig())
            home_v2 = app.screens["home_v2"]
            labels: list[str] = []
            self._collect_text(home_v2, labels)
            self.assertNotIn("Schema Project PyQt Experiment", "\n".join(labels))

    def test_home_v2_shows_and_launches_pyqt_experiment_card_when_gate_enabled(self) -> None:
        with mock.patch.dict(os.environ, {EXPERIMENT_ENV_VAR: "1"}, clear=False), mock.patch(
            "src.gui.v2.routes.home_impl.launch_pyqt_schema_project",
            return_value=(True, "started"),
        ) as launch_mock, mock.patch("src.gui.v2.routes.home_impl.messagebox.showinfo") as info_mock, mock.patch(
            "src.gui.v2.routes.home_impl.messagebox.showwarning"
        ) as warn_mock:
            app = App(self.root, AppConfig())
            home_v2 = app.screens["home_v2"]
            labels: list[str] = []
            self._collect_text(home_v2, labels)
            self.assertIn("Schema Project PyQt Experiment", "\n".join(labels))

            button = self._find_experiment_open_button(home_v2)
            self.assertIsNotNone(button)
            assert button is not None
            button.invoke()

            launch_mock.assert_called_once()
            info_mock.assert_called_once()
            warn_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
