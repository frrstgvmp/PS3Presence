"""Render the compact UI offline, without touching credentials or statistics."""
from __future__ import annotations

import argparse
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from runtime_bootstrap import prepare_native_libraries
prepare_native_libraries()

from PySide6.QtCore import QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from bridge import BridgePhase, BridgeSnapshot
from game_statistics import GameTimeTracker
from presence_parser import LegacyPresence
from qml_app import PresenceController, QML_FILE, ICON_FILE
from settings_store import StoredConfiguration
from startup_screen import StartupScreen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.Software)
    QQuickStyle.setStyle("Basic")
    app = QApplication([])
    with ExitStack() as stack:
        stack.enter_context(patch("qml_app.load_npsso", return_value="test"))
        stack.enter_context(patch("qml_app.load_npsso_expires_at", return_value=None))
        stack.enter_context(patch("qml_app.load_configuration", return_value=StoredConfiguration(theme_id="aurora", language="en")))
        controller = PresenceController(statistics_path=None)
        controller._clock.stop()
        controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "Ready", "lapami_vverh", discord_connected=True))
        controller._bridge_expires_at = time.time() + 32*86400 + 4*3600 + 14*60 + 22
        controller._refresh_auth()
        for event in ("Watching legacy PSN presence for lapami_vverh.", "Discord RPC connected.", "Discord cleared: no active PS3 game returned by PSN."):
            controller.append_log(event)
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("presence", controller)
        engine.load(QUrl.fromLocalFile(str(QML_FILE)))
        if not engine.rootObjects():
            return 1
        window = engine.rootObjects()[0]
        window.show()
        QTest.qWait(250)
        for name, prop in (("main", None), ("about", "aboutVisible"), ("settings", "settingsVisible"), ("npsso", "npssoVisible"), ("statistics", "statisticsVisible"), ("decorations", "decorationsEnabled")):
            if prop:
                window.setProperty(prop, True)
            QTest.qWait(250)
            if not window.grabWindow().save(str(args.output / (name + ".png"))):
                return 2
            if name == "about":
                phrase = window.findChild(QObject, "aboutSunPraise")
                timeline = phrase.findChild(QObject, "sunPraiseTimeline")
                timeline.setProperty("paused", True)
                for phase, elapsed in (("falling", 600), ("assembled", 2400), ("scattering", 6800)):
                    phrase.setProperty("elapsed", elapsed)
                    QTest.qWait(50)
                    if not window.grabWindow().save(str(args.output / ("about-" + phase + ".png"))):
                        return 2
                phrase.setProperty("elapsed", 2400)
                QTest.mouseClick(window, Qt.LeftButton,
                    pos=phrase.mapToScene(QPointF(phrase.width()/2, phrase.height()/2)).toPoint())
                burst = phrase.findChild(QObject, "sunPraiseBurstAnimation")
                burst.setProperty("paused", True)
                phrase.setProperty("burstElapsed", 260)
                QTest.qWait(50)
                if not window.grabWindow().save(str(args.output / "about-burst.png")):
                    return 2
                timeline.setProperty("paused", False)
            if prop:
                window.setProperty(prop, False)
        controller._language = "ru"
        controller._refresh_auth()
        controller.language_changed.emit()
        for name, prop in (("main-ru", None), ("about-ru", "aboutVisible"), ("settings-ru", "settingsVisible"), ("npsso-ru", "npssoVisible")):
            if prop:
                window.setProperty(prop, True)
            QTest.qWait(150)
            window.grabWindow().save(str(args.output / (name + ".png")))
            if prop:
                window.setProperty(prop, False)
        controller._language = "en"
        controller._refresh_auth()
        controller.language_changed.emit()
        clock = [0.0]
        controller._statistics = GameTimeTracker(None, clock=lambda: clock[0], wall_clock=lambda: 1791280800 + clock[0])
        game = LegacyPresence("online", "PS3", "inFamous", "BCES00609", "PlayStation 3", None)
        controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "Playing", "lapami_vverh", game, True))
        for _ in range(4800):
            clock[0] += 1
            if int(clock[0]) % 30 == 0:
                controller._statistics.observe(game, "lapami_vverh")
            controller._statistics.advance()
        controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "Ready", "lapami_vverh", discord_connected=True))
        controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "Playing", "lapami_vverh", game, True))
        QTest.qWait(200)
        window.grabWindow().save(str(args.output / "playing.png"))
        window.setProperty("statisticsVisible", True)
        QTest.qWait(200)
        window.grabWindow().save(str(args.output / "statistics-populated.png"))
        window.findChild(QObject, "gameStatisticsDialog").setProperty("historyMode", True)
        QTest.qWait(200)
        window.grabWindow().save(str(args.output / "sessions.png"))
        dialog = window.findChild(QObject, "gameStatisticsDialog")
        dialog.setProperty("historyMode", False)
        controller.gameStatistics.update([
            dict(gameKey=str(i), title=title, coverUrl="", playtime="12:35:21",
                 sessionCount=10, isCurrent=False, isPaused=False, lastPlayed="4 October 2026 · 23:13")
            for i, title in enumerate(("inFamous 2", "inFamous", "Test game"))
        ])
        QTest.qWait(200)
        window.grabWindow().save(str(args.output / "statistics-scroll-top.png"))
        view = window.findChild(QObject, "gameStatisticsList")
        view.setProperty("contentY", view.property("originY") + view.property("contentHeight") - view.property("height"))
        QTest.qWait(100)
        window.grabWindow().save(str(args.output / "statistics-scroll-bottom.png"))
        window.setProperty("statisticsVisible", False)
        controller._theme_id = "light"
        controller.changed.emit()
        QTest.qWait(200)
        window.grabWindow().save(str(args.output / "light.png"))
        splash = StartupScreen(QIcon(str(ICON_FILE)))
        splash.show()
        QTest.qWait(100)
        splash.grab().save(str(args.output / "splash.png"))
        splash.close()
        controller.garlandAudio.shutdown()
        window.hide()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
