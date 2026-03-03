from __future__ import annotations


def build_columns_panel(self):  # type: ignore[override]
    panel = SchemaEditorBaseScreen.build_columns_panel(self)
    editor_box = self._find_column_editor_box(panel)
    if editor_box is not None:
        self._install_generator_form_host(editor_box)
    return panel

def build_header(self):  # type: ignore[override]
    spacing = V2_THEME.spacing
    type_scale = V2_THEME.type_scale
    header_parent = self._header_host if hasattr(self, "_header_host") else self._root_content
    header = tk.Frame(header_parent, bg=V2_HEADER_BG, height=58)
    header.pack(fill="x", pady=(0, spacing.md))
    header.pack_propagate(False)

    tk.Button(
        header,
        text="Back",
        command=self._on_back_requested,
        padx=spacing.md,
        pady=spacing.sm - spacing.xs,
        **v2_button_options("secondary"),
    ).pack(side="left", padx=(spacing.sm, spacing.sm), pady=spacing.sm)
    tk.Label(
        header,
        text="Schema Project v2",
        bg=V2_HEADER_BG,
        fg=V2_HEADER_FG,
        font=type_scale.page_title,
    ).pack(side="left", pady=spacing.sm)
    tk.Label(
        header,
        textvariable=self._dirty_indicator_var,
        bg=V2_HEADER_BG,
        fg=V2_HEADER_FG,
        font=type_scale.body_bold,
    ).pack(side="left", padx=(spacing.md, 0), pady=spacing.sm)

    mode_group = tk.Frame(header, bg=V2_HEADER_BG)
    mode_group.pack(side="left", padx=(spacing.md, 0), pady=spacing.sm)
    tk.Label(
        mode_group,
        text="Mode",
        bg=V2_HEADER_BG,
        fg=V2_HEADER_FG,
        font=type_scale.body_small,
    ).pack(side="left", padx=(0, spacing.xs))
    for mode_value, label in (("simple", "Simple"), ("medium", "Medium"), ("complex", "Complex")):
        tk.Radiobutton(
            mode_group,
            text=label,
            value=mode_value,
            variable=self.schema_design_mode_var,
            indicatoron=0,
            bd=1,
            relief="solid",
            padx=spacing.sm,
            pady=spacing.xs,
            bg=V2_HEADER_BG,
            fg=V2_HEADER_FG,
            activebackground=V2_HEADER_BG,
            activeforeground=V2_HEADER_FG,
            selectcolor=V2_HEADER_BG,
            highlightthickness=0,
        ).pack(side="left", padx=(0, spacing.xs))

    tk.Button(
        header,
        text="Shortcuts",
        command=self._show_shortcuts_help,
        padx=spacing.md,
        pady=spacing.sm - spacing.xs,
        **v2_button_options("secondary"),
    ).pack(side="right", padx=(0, spacing.sm), pady=spacing.sm)
    tk.Button(
        header,
        text="Notifications",
        command=self._show_notifications_history,
        padx=spacing.md,
        pady=spacing.sm - spacing.xs,
        **v2_button_options("secondary"),
    ).pack(side="right", padx=(0, spacing.sm), pady=spacing.sm)
    return header

def _on_back_requested(self) -> None:
    if self.confirm_discard_or_save(action_name="returning to Schema Studio v2"):
        self.app.show_screen("schema_studio_v2")

