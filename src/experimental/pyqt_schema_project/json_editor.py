from __future__ import annotations

import json

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class JsonEditorDialog(QDialog):
    """Minimal JSON editor with parse feedback."""

    def __init__(self, parent: QWidget | None, *, title: str, initial_text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 520)

        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(initial_text)
        layout.addWidget(self.editor)

        self.message = QLabel("", self)
        layout.addWidget(self.message)

        actions = QHBoxLayout()
        self.format_btn = QPushButton("Format", self)
        self.format_btn.clicked.connect(self._format_json)
        actions.addWidget(self.format_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _format_json(self) -> None:
        payload = self._parse_json()
        if payload is None:
            return
        self.editor.setPlainText(json.dumps(payload, indent=2, sort_keys=True))
        self.message.setText("JSON formatted.")

    def _parse_json(self):  # noqa: ANN201
        text = self.editor.toPlainText().strip()
        if text == "":
            self.message.setText("Blank content is allowed and will be treated as empty JSON.")
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            self.message.setText(f"Parse error at line {exc.lineno}, column {exc.colno}: {exc.msg}")
            QMessageBox.warning(
                self,
                "JSON parse warning",
                f"JSON editor: invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno}). "
                "Fix: correct the syntax and retry.",
            )
            return None

    def _accept_if_valid(self) -> None:
        text = self.editor.toPlainText().strip()
        if text != "":
            payload = self._parse_json()
            if payload is None:
                return
        self.accept()

    @property
    def text(self) -> str:
        return self.editor.toPlainText().strip()

    @staticmethod
    def edit_json(parent: QWidget | None, *, title: str, initial_text: str) -> tuple[bool, str]:
        dialog = JsonEditorDialog(parent, title=title, initial_text=initial_text)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return accepted, dialog.text


__all__ = ["JsonEditorDialog"]
