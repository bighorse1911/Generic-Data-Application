from __future__ import annotations


def _register_shortcuts(self) -> None:
    manager = self.shortcut_manager
    manager.register_ctrl_cmd("f", "Focus table search", self._focus_table_search)
    manager.register_ctrl_cmd("f", "Focus columns search", self._focus_columns_search, shift=True)
    manager.register("<Alt-f>", "Focus relationship search", self._focus_fk_search, aliases=["<Option-f>"])
    manager.register("<F6>", "Focus next section", self._focus_next_anchor)
    manager.register("<Shift-F6>", "Focus previous section", self._focus_previous_anchor)

    manager.register_ctrl_cmd("s", "Save project JSON", self._save_project)
    manager.register_ctrl_cmd("o", "Load project JSON", self._load_project)
    manager.register_ctrl_cmd("r", "Run validation", self._run_validation_full)
    manager.register_ctrl_cmd("Return", "Generate sample data", self._on_generate_sample)

    manager.register_ctrl_cmd("z", "Undo", self._undo_last_change)
    manager.register_ctrl_cmd("y", "Redo", self._redo_last_change)
    manager.register_ctrl_cmd("z", "Redo", self._redo_last_change, shift=True)
    manager.register("<F1>", "Show shortcut help", self._show_shortcuts_help)


def _register_focus_anchors(self) -> None:
    controller = self.focus_controller
    controller.add_anchor(
        "tables_search",
        lambda: getattr(getattr(self, "tables_search", None), "entry", None),
        description="Tables search",
    )
    controller.add_anchor(
        "tables_list",
        lambda: getattr(self, "tables_list", None),
        description="Tables list",
    )
    controller.add_anchor(
        "columns_search",
        lambda: getattr(getattr(self, "columns_search", None), "entry", None),
        description="Columns search",
    )
    controller.add_anchor(
        "columns_tree",
        lambda: getattr(self, "columns_tree", None),
        description="Columns table",
    )
    controller.add_anchor(
        "fk_search",
        lambda: getattr(getattr(self, "fk_search", None), "entry", None),
        description="Relationships search",
    )
    controller.add_anchor(
        "fks_tree",
        lambda: getattr(self, "fks_tree", None),
        description="Relationships table",
    )
    controller.add_anchor(
        "preview_tree",
        lambda: getattr(self, "preview_tree", None),
        description="Preview table",
    )
    controller.set_default_anchor("tables_search")

