"""Undo/redo command protocol and bounded command stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar, runtime_checkable

__all__ = ["UndoCommand", "SnapshotCommand", "UndoStack"]

StateT = TypeVar("StateT")


@runtime_checkable
class UndoCommand(Protocol):
    """Command contract for reversible UI actions."""

    label: str

    def do(self) -> None:
        """Apply the command."""

    def undo(self) -> None:
        """Reverse the command."""

    def redo(self) -> None:
        """Re-apply the command after undo."""


@dataclass(frozen=True)
class SnapshotCommand(Generic[StateT]):
    """
    Reversible command backed by before/after state snapshots.

    `apply_state` must fully restore the provided state.
    """

    label: str
    apply_state: Callable[[StateT], None]
    before_state: StateT
    after_state: StateT

    def do(self) -> None:
        self.apply_state(self.after_state)

    def undo(self) -> None:
        self.apply_state(self.before_state)

    def redo(self) -> None:
        self.apply_state(self.after_state)


class UndoStack:
    """Bounded undo/redo stack with standard push/undo/redo semantics."""

    def __init__(self, *, limit: int = 100) -> None:
        if int(limit) <= 0:
            raise ValueError(
                "Undo stack: limit must be > 0. "
                "Fix: set a positive undo history limit."
            )
        self._limit = int(limit)
        self._undo: list[UndoCommand] = []
        self._redo: list[UndoCommand] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_label(self) -> str | None:
        if not self._undo:
            return None
        return str(self._undo[-1].label)

    @property
    def redo_label(self) -> str | None:
        if not self._redo:
            return None
        return str(self._redo[-1].label)

    def push(self, command: UndoCommand) -> None:
        label = str(getattr(command, "label", "")).strip()
        if label == "":
            raise ValueError(
                "Undo stack: command label is required. "
                "Fix: provide a non-empty command label."
            )
        self._undo.append(command)
        self._redo.clear()
        overflow = len(self._undo) - self._limit
        if overflow > 0:
            del self._undo[:overflow]

    def run(self, command: UndoCommand) -> None:
        command.do()
        self.push(command)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def undo(self) -> UndoCommand | None:
        if not self._undo:
            return None
        command = self._undo.pop()
        try:
            command.undo()
        except Exception:
            self._undo.append(command)
            raise
        self._redo.append(command)
        return command

    def redo(self) -> UndoCommand | None:
        if not self._redo:
            return None
        command = self._redo.pop()
        try:
            command.redo()
        except Exception:
            self._redo.append(command)
            raise
        self._undo.append(command)
        return command
