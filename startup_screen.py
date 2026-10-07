"""Small branded startup window; shown only for an interactive launch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen
from localization import DEFAULT_LANGUAGE, translate


class StartupScreen(QSplashScreen):
    def __init__(self, icon: QIcon, *, language: str = DEFAULT_LANGUAGE) -> None:
        pixmap = QPixmap(264, 112)
        pixmap.fill(QColor("#101b28"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#405971"))
        painter.drawRect(0, 0, 263, 111)
        mark = QIcon(str(Path(__file__).resolve().parent / "assets" / "presence-mark.svg"))
        (mark if not mark.isNull() else icon).paint(painter, 16, 18, 40, 40)
        painter.setFont(QFont("Segoe UI", 17, QFont.DemiBold))
        painter.setPen(QColor("#8ab5dc"))
        painter.drawText(68, 45, "PS3")
        painter.setPen(QColor("#eef5fc"))
        painter.drawText(116, 45, "PRESENCE")
        painter.end()
        super().__init__(pixmap)
        self._language = language
        self._status = translate("Подготовка интерфейса…", language)
        self._progress = 0.15

    def set_stage(self, status: str, progress: float) -> None:
        self._status = translate(status, self._language)
        self._progress = progress
        self.repaint()

    def drawContents(self, painter: QPainter) -> None:
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#a1b4c5"))
        painter.drawText(16, 79, self._status)
        painter.fillRect(16, 95, 232, 2, QColor("#243342"))
        painter.fillRect(16, 95, int(232 * self._progress), 2, QColor("#8ab5dc"))
