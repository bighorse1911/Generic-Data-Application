import unittest

from src.gui_kit.undo import SnapshotCommand, UndoStack


class TestGuiKitUndo(unittest.TestCase):
    def test_snapshot_command_do_undo_redo(self) -> None:
        state = {"value": 0}

        def _apply(value: int) -> None:
            state["value"] = value

        command = SnapshotCommand[int](
            label="Set value",
            apply_state=_apply,
            before_state=0,
            after_state=5,
        )

        command.do()
        self.assertEqual(state["value"], 5)
        command.undo()
        self.assertEqual(state["value"], 0)
        command.redo()
        self.assertEqual(state["value"], 5)

    def test_undo_stack_clears_redo_on_new_push(self) -> None:
        state = {"value": 0}
        stack = UndoStack(limit=10)

        def _apply(value: int) -> None:
            state["value"] = value

        first = SnapshotCommand[int](
            label="Set to 1",
            apply_state=_apply,
            before_state=0,
            after_state=1,
        )
        second = SnapshotCommand[int](
            label="Set to 2",
            apply_state=_apply,
            before_state=1,
            after_state=2,
        )
        third = SnapshotCommand[int](
            label="Set to 3",
            apply_state=_apply,
            before_state=1,
            after_state=3,
        )

        stack.run(first)
        stack.run(second)
        stack.undo()
        self.assertEqual(state["value"], 1)
        self.assertTrue(stack.can_redo)

        stack.run(third)
        self.assertEqual(state["value"], 3)
        self.assertFalse(stack.can_redo)

    def test_undo_stack_limit_discards_oldest_commands(self) -> None:
        state = {"value": 0}
        stack = UndoStack(limit=2)

        def _apply(value: int) -> None:
            state["value"] = value

        stack.run(SnapshotCommand[int]("Set to 1", _apply, 0, 1))
        stack.run(SnapshotCommand[int]("Set to 2", _apply, 1, 2))
        stack.run(SnapshotCommand[int]("Set to 3", _apply, 2, 3))

        stack.undo()
        self.assertEqual(state["value"], 2)
        stack.undo()
        self.assertEqual(state["value"], 1)
        self.assertIsNone(stack.undo())
        self.assertEqual(state["value"], 1)


if __name__ == "__main__":
    unittest.main()
