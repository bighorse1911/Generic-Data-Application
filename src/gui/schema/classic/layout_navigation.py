from __future__ import annotations


def _on_back_requested(self) -> None:
    if self._confirm_discard_or_save("returning to Home"):
        self.app.go_home()


def _browse_db_path(self) -> None:
    path = filedialog.asksaveasfilename(
        title="Choose SQLite database file",
        defaultextension=".db",
        filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
    )
    if path:
        self.db_path_var.set(path)

