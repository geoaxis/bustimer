"""
QAbstractListModel exposing bus departure rows to QML.
Each row represents one bus and its paired train connection.
"""

from PyQt6.QtCore import QAbstractListModel, Qt, pyqtSignal, QModelIndex, pyqtSlot
from dataclasses import dataclass
import enum


class ConnectionStatus(enum.IntEnum):
    UNKNOWN = 0
    SAFE = 1    # green  — made it with buffer
    TIGHT = 2   # amber  — within buffer window
    MISS = 3    # red    — can't make it


@dataclass
class BusRow:
    # Bus fields
    line: str = ""
    destination: str = ""
    minutes: int = 0            # minutes until bus departs (from now)
    bus_scheduled: str = ""     # "HH:MM"
    bus_expected: str = ""      # "HH:MM"
    bus_delay_minutes: int = 0  # > 0 means late

    # Paired train fields
    train_line: str = ""
    train_destination: str = ""
    train_scheduled: str = ""   # "HH:MM"
    train_expected: str = ""    # "HH:MM"
    train_delay_minutes: int = 0
    change_minutes: int = 0     # minutes spare at the station
    arrive_time: str = ""       # "HH:MM" — estimated arrival at Stockholm C
    arrive_minutes: int = 0     # minutes from now until arrival at destination

    status: ConnectionStatus = ConnectionStatus.UNKNOWN


# QML role names — must match property names used in QML delegate
_ROLES = {
    Qt.ItemDataRole.UserRole + 0: b"line",
    Qt.ItemDataRole.UserRole + 1: b"destination",
    Qt.ItemDataRole.UserRole + 2: b"minutes",
    Qt.ItemDataRole.UserRole + 3: b"busScheduled",
    Qt.ItemDataRole.UserRole + 4: b"busExpected",
    Qt.ItemDataRole.UserRole + 5: b"busDelayMinutes",
    Qt.ItemDataRole.UserRole + 6: b"trainLine",
    Qt.ItemDataRole.UserRole + 7: b"trainDestination",
    Qt.ItemDataRole.UserRole + 8: b"trainScheduled",
    Qt.ItemDataRole.UserRole + 9: b"trainExpected",
    Qt.ItemDataRole.UserRole + 10: b"trainDelayMinutes",
    Qt.ItemDataRole.UserRole + 11: b"status",
    Qt.ItemDataRole.UserRole + 12: b"changeMinutes",
    Qt.ItemDataRole.UserRole + 13: b"arriveTime",
    Qt.ItemDataRole.UserRole + 14: b"arriveMinutes",
}

_ROLE_ATTR = {role: name.decode() for role, name in _ROLES.items()}
# camelCase → snake_case mapping for dataclass fields
_CAMEL_TO_SNAKE = {
    "busScheduled": "bus_scheduled",
    "busExpected": "bus_expected",
    "busDelayMinutes": "bus_delay_minutes",
    "trainLine": "train_line",
    "trainDestination": "train_destination",
    "trainScheduled": "train_scheduled",
    "trainExpected": "train_expected",
    "trainDelayMinutes": "train_delay_minutes",
    "changeMinutes": "change_minutes",
    "arriveTime": "arrive_time",
    "arriveMinutes": "arrive_minutes",
}


class BusModel(QAbstractListModel):
    rowsChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[BusRow] = []

    # ── QAbstractListModel overrides ──────────────────────────────────────

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        attr = _ROLE_ATTR.get(role)
        if attr is None:
            return None
        snake = _CAMEL_TO_SNAKE.get(attr, attr)
        value = getattr(row, snake, None)
        # Convert enum to int for QML
        if isinstance(value, ConnectionStatus):
            return int(value)
        return value

    def roleNames(self):
        return _ROLES

    # ── Public API — must be called on the GUI thread ─────────────────────

    @pyqtSlot(object)
    def update(self, rows):
        """Replace all rows atomically. Connected via Qt queued connection."""
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.rowsChanged.emit()
