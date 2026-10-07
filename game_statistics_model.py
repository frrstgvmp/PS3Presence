"""Incremental Qt model: ticking playtime does not recreate cover delegates."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class GameStatisticsModel(QAbstractListModel):
    KEY_FIELD = "gameKey"
    FIELDS = ("gameKey", "title", "coverUrl", "playtime", "sessionCount", "isCurrent", "isPaused", "lastPlayed")
    ROLES = {int(Qt.UserRole) + i + 1: field for i, field in enumerate(FIELDS)}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def roleNames(self):
        return {role: field.encode() for role, field in self.ROLES.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(self.ROLES.get(role, ""))

    def update(self, rows):
        if [row[self.KEY_FIELD] for row in rows] != [row[self.KEY_FIELD] for row in self._rows]:
            self.beginResetModel()
            self._rows = rows
            self.endResetModel()
            return
        for i, (old, new) in enumerate(zip(self._rows, rows)):
            changed = [role for role, field in self.ROLES.items() if old.get(field) != new.get(field)]
            self._rows[i] = new
            if changed:
                self.dataChanged.emit(self.index(i), self.index(i), changed)


class SessionHistoryModel(GameStatisticsModel):
    KEY_FIELD = "sessionKey"
    FIELDS = ("sessionKey", "title", "coverUrl", "playtime", "startedAt", "endedAt", "state", "isCurrent", "isPaused")
    ROLES = {int(Qt.UserRole) + i + 1: field for i, field in enumerate(FIELDS)}
