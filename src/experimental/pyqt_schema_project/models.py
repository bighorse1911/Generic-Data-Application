from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DictTableModel(QAbstractTableModel):
    """Simple dict-backed table model for experimental PyQt tables."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[str, object]] = []
        self._columns: list[str] = []

    def set_rows(self, rows: Iterable[dict[str, object]], columns: list[str] | None = None) -> None:
        self.beginResetModel()
        self._rows = [dict(row) for row in rows]
        if columns is not None:
            self._columns = list(columns)
        else:
            inferred: list[str] = []
            for row in self._rows:
                for key in row.keys():
                    if key not in inferred:
                        inferred.append(key)
            self._columns = inferred
        self.endResetModel()

    def rowCount(self, _parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, _parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: ANN201
        if not index.isValid() or role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        row = self._rows[index.row()]
        key = self._columns[index.column()]
        value = row.get(key)
        if value is None:
            return ""
        return str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: ANN201,N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
            return ""
        return str(section + 1)


__all__ = ["DictTableModel"]
