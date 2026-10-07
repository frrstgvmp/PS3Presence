"""Offline checks of the actual packaged runtime, without credential writes."""
from __future__ import annotations

import time
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QSslSocket

from app_metadata import VERSION


def run_release_checks(app, controller, engine, window, themes, *, with_audio=False,
                       expected_graphics_api=None) -> int:
    controller._clock.stop()
    controller._new_year_visibility_override = True
    controller._theme_id = "newyear"
    controller.changed.emit()
    window.setProperty("decorationsEnabled", True)
    window.show()
    audio = controller.garlandAudio
    warnings = []
    audio.warning.connect(warnings.append)
    engine.warnings.connect(lambda messages: warnings.extend(str(message) for message in messages))
    dialogs = ("settingsVisible", "npssoVisible", "statisticsVisible", "aboutVisible")
    states = [(theme, dialog) for theme in themes for dialog in (None, *dialogs, "sessionHistory")]
    stage = 0
    awaiting_frame = False
    audio_started = None
    checks = QTimer(app)
    checks.setInterval(75)

    def check_release():
        nonlocal stage, awaiting_frame, audio_started
        if warnings:
            if sys.stderr is not None:
                print("Release check warnings:", warnings, file=sys.stderr)
            app.exit(2)
            return
        if audio.readyCount != 36:
            return
        version_label = window.findChild(QObject, "programVersion")
        conditions = {
            "ssl": QSslSocket.supportsSsl(),
            "version": version_label is not None and version_label.property("text") == "v. " + VERSION,
            "frame": not window.grabWindow().isNull(),
            "art": not QImage(str(Path(__file__).resolve().parent / "assets" / "newyear-theme.png")).isNull(),
            "renderer": expected_graphics_api is None or window.rendererInterface().graphicsApi() == expected_graphics_api,
        }
        if not all(conditions.values()):
            if sys.stderr is not None:
                print("Release check failed:", conditions, "stage", stage, file=sys.stderr)
            app.exit(2)
            return
        if stage < len(states):
            if awaiting_frame:
                stage += 1
                awaiting_frame = False
            else:
                theme, dialog = states[stage]
                controller._theme_id = theme
                controller.changed.emit()
                for name in dialogs:
                    window.setProperty(name, False)
                statistics_dialog = window.findChild(QObject, "gameStatisticsDialog")
                statistics_dialog.setProperty("historyMode", dialog == "sessionHistory")
                if dialog == "sessionHistory":
                    window.setProperty("statisticsVisible", True)
                elif dialog:
                    window.setProperty(dialog, True)
                awaiting_frame = True
            return
        if with_audio:
            if audio_started is None:
                for name in dialogs:
                    window.setProperty(name, False)
                controller._theme_id = "newyear"
                controller.changed.emit()
                for lamp in (0, 1, 2):
                    audio.enter(lamp)
                    audio.leave(lamp)
                audio_started = time.monotonic()
                if len(audio._voices) != 3:
                    app.exit(2)
                return
            if time.monotonic() - audio_started < 1.3:
                return
            if audio._voices or warnings:
                app.exit(2)
                return
        app.exit(0)

    checks.timeout.connect(check_release)
    checks.start()
    QTimer.singleShot(60_000, app, lambda: app.exit(3))
    return app.exec()
