from __future__ import annotations

def _erd_error(self, field: str, issue: str, hint: str) -> str:
        return f"ERD Designer / {field}: {issue}. Fix: {hint}."


def _show_error_dialog(self, location: str, message: object) -> str:
        return self.error_surface.emit_exception_actionable(
            message,
            location=(str(location).strip() or "ERD designer"),
            hint="review the inputs and retry",
            mode="mixed",
        )


def _set_combo_values(
        self,
        combo: ttk.Combobox,
        *,
        values: list[str],
        variable: tk.StringVar,
    ) -> None:
        combo.configure(values=tuple(values))
        current = variable.get().strip()
        if current in values:
            variable.set(current)
            return
        if values:
            variable.set(values[0])
            return
        variable.set("")


def _table_names(self) -> list[str]:
        if self.project is None:
            return []
        return [table.table_name for table in self.project.tables]


def _table_for_name(self, table_name: str) -> object | None:
        if self.project is None:
            return None
        for table in self.project.tables:
            if table.table_name == table_name:
                return table
        return None


def _columns_for_table(self, table_name: str, *, primary_key_only: bool = False) -> list[str]:
        if self.project is None:
            return []
        for table in self.project.tables:
            if table.table_name != table_name:
                continue
            if primary_key_only:
                return [column.name for column in table.columns if column.primary_key]
            return [column.name for column in table.columns]
        return []
