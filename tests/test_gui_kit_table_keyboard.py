import tkinter as tk
from tkinter import ttk
import unittest

from src.gui_kit.table_keyboard import install_treeview_keyboard_support


class TestTableKeyboardSupport(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.geometry("420x260")

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _build_tree(self, *, rows: int = 6) -> ttk.Treeview:
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=("id", "value"), show="headings", height=3)
        tree.heading("id", text="id")
        tree.heading("value", text="value")
        tree.column("id", width=80, anchor="w")
        tree.column("value", width=140, anchor="w")
        tree.pack(fill="both", expand=True)
        for idx in range(rows):
            tree.insert("", "end", values=(idx, f"row-{idx}"))
        install_treeview_keyboard_support(tree, include_headers=True)
        self.root.update()
        if tree.get_children():
            first = tree.get_children()[0]
            tree.selection_set(first)
            tree.focus(first)
        tree.focus_set()
        self.root.update()
        return tree

    def _send(self, tree: ttk.Treeview, sequence: str) -> None:
        self.root.focus_force()
        tree.focus_set()
        tree.event_generate(sequence, when="tail")
        self.root.update()

    def test_select_all_and_copy_with_without_headers(self) -> None:
        tree = self._build_tree(rows=4)

        self._send(tree, "<Control-a>")
        self.assertEqual(len(tree.selection()), 4)

        first = tree.get_children()[0]
        tree.selection_set(first)
        tree.focus(first)
        self._send(tree, "<Control-c>")
        with_headers = self.root.clipboard_get()
        self.assertTrue(with_headers.startswith("id\tvalue"))

        self._send(tree, "<Control-Shift-C>")
        without_headers = self.root.clipboard_get()
        self.assertFalse(without_headers.startswith("id\tvalue"))

    def test_page_and_end_home_navigation_with_no_selection_recovery(self) -> None:
        tree = self._build_tree(rows=8)
        tree.selection_remove(tree.selection())
        tree.focus("")

        self._send(tree, "<Next>")
        selection = tree.selection()
        self.assertTrue(selection)

        self._send(tree, "<Control-End>")
        last_item = tree.get_children()[-1]
        self.assertEqual(tree.selection()[0], last_item)

        self._send(tree, "<Control-Home>")
        first_item = tree.get_children()[0]
        self.assertEqual(tree.selection()[0], first_item)

    def test_empty_tree_navigation_is_safe(self) -> None:
        tree = self._build_tree(rows=0)
        self._send(tree, "<Control-a>")
        self._send(tree, "<Control-End>")
        self._send(tree, "<Next>")
        self.assertEqual(tree.selection(), ())


if __name__ == "__main__":
    unittest.main()


