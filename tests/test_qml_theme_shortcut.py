from __future__ import annotations

import os
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QImage, QPainter, QFontMetricsF

from bridge import BridgePhase, BridgeSnapshot
from app_metadata import VERSION
from qml_app import PresenceController, QML_FILE, SecretThemeKeyFilter, show_main_window
from transparent_animation import TransparentGif
from settings_store import StoredConfiguration
from game_statistics import GameTimeTracker
from tests.test_game_statistics import Clock, GAME, OTHER
from dataclasses import replace
from time_format import format_russian_date
from datetime import datetime
import settings_store


class SeasonalThemeShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def create_window(self, stack):
        stack.enter_context(patch("qml_app.load_local_cover_index", return_value={}))
        stack.enter_context(patch("qml_app.is_new_year_theme_available", return_value=False))
        stack.enter_context(patch("qml_app.load_npsso", return_value="test"))
        stack.enter_context(patch("qml_app.load_npsso_expires_at", return_value=None))
        stack.enter_context(patch("qml_app.load_configuration", return_value=StoredConfiguration(theme_id="botanical", language="ru")))
        stack.enter_context(patch("qml_app.save_theme", side_effect=lambda theme: theme))
        controller = PresenceController(statistics_path=None)
        controller._clock.stop()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("presence", controller)
        engine.load(QUrl.fromLocalFile(str(QML_FILE)))
        self.assertEqual(len(engine.rootObjects()), 1)
        window = engine.rootObjects()[0]
        window.show()
        window.requestActivate()
        QTest.qWait(80)
        return controller, engine, window

    def find_visual_item(self, window, name):
        def find(item):
            if item.objectName() == name:
                return item
            for child in item.childItems():
                result = find(child)
                if result is not None:
                    return result
            return None
        return find(window.contentItem())

    def test_default_theme_is_aurora_in_controller_and_qml(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            with patch("qml_app.load_configuration", return_value=StoredConfiguration()):
                default_controller = PresenceController(statistics_path=None)
                default_controller._clock.stop()
                self.assertEqual(default_controller.themeId, "aurora")
                self.assertEqual(default_controller.language, "ru")
                self.assertEqual(default_controller.phase, "Подключение")
                controller._theme_id = default_controller.themeId
                controller.changed.emit()
                self.app.processEvents()
                self.assertEqual(window.property("currentThemeIndex"), 6)
                controller._theme_id = "unknown"
                controller.changed.emit()
                self.app.processEvents()
                self.assertEqual(window.property("currentThemeIndex"), 6)
            window.hide()

    def art_point(self, window, x, y):
        artwork = self.find_visual_item(window, "decorationArtwork")
        return artwork.mapToScene(QPointF(x, y)).toPoint()

    def previous_art_point(self, window, x, y):
        # Existing pixel-mask samples were measured at the previous 90% scale.
        return self.art_point(window, x / .9, y / .9)

    def test_compact_dashboard_and_decoration_toggle_in_every_theme(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            self.assertEqual((window.width(), window.height()), (390, 526))
            self.assertFalse(window.property("decorationsEnabled"))
            self.assertFalse(controller.garlandAudio.active)
            controller.toggleNewYearThemeButton()
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            toggle = self.find_visual_item(window, "decorationToggle")
            point = toggle.mapToScene(QPointF(toggle.width()/2, toggle.height()/2)).toPoint()
            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora", "newyear"):
                controller.saveTheme(theme)
                self.app.processEvents()
                artwork = self.find_visual_item(window, "decorationArtwork")
                divider = self.find_visual_item(window, "toolbarDivider")
                divider_y = divider.mapToScene(QPointF(0, 0)).y()
                for name in ("decorationArtwork", "garlandLayer", "decorationTargets"):
                    layer = self.find_visual_item(window, name)
                    self.assertAlmostEqual(layer.mapToScene(QPointF(0, 0)).y(), divider_y, delta=.1, msg=(theme, name))
                self.assertFalse(artwork.isVisible(), theme)
                self.assertEqual(artwork.property("source").toString(), "", theme)
                self.assertIsNone(self.find_visual_item(window, "secretLeafClick"))
                self.assertIsNone(self.find_visual_item(window, "festivePineconeClick"))
                for name in ("mainToolbar", "gamePanel", "authorizationRow", "eventLogPanel", "reconnectDiscordButton", "presenceStatus"):
                    item = self.find_visual_item(window, name)
                    origin = item.mapToScene(QPointF(0, 0))
                    self.assertGreaterEqual(origin.x(), 0, (theme, name))
                    self.assertGreaterEqual(origin.y(), 0, (theme, name))
                    self.assertLessEqual(origin.x() + item.width(), window.width() + 1, (theme, name))
                    self.assertLessEqual(origin.y() + item.height(), window.height() + 1, (theme, name))
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertTrue(window.property("decorationsEnabled"), theme)
                self.assertTrue(artwork.isVisible(), theme)
                lamp = self.find_visual_item(window, "garlandLamp0")
                QTest.mouseClick(window, Qt.LeftButton, pos=self.art_point(window, lamp.x()+130, lamp.y()+260))
                self.assertTrue(lamp.property("lit"), theme)
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertFalse(window.property("decorationsEnabled"), theme)
                self.assertFalse(lamp.property("lit"), theme)
                self.assertFalse(controller.garlandAudio.active, theme)
                self.assertFalse(self.find_visual_item(window, "botanicalLeafFall").property("active"), theme)
                self.assertFalse(window.findChild(QObject, "festiveSnowfall").property("active"), theme)
            self.assertFalse(warnings, warnings)
            heading = self.find_visual_item(window, "programHeading")
            logo = self.find_visual_item(window, "programLogo")
            self.assertEqual(heading.property("text"), "PS3 PRESENCE")
            # The title keeps its left edge; the logo is centered in the space before it.
            self.assertAlmostEqual(heading.mapToScene(QPointF(0, 0)).x(), 64, delta=1)
            self.assertAlmostEqual(logo.mapToScene(QPointF(logo.width()/2, logo.height()/2)).x(), 32, delta=1)
            self.assertIsNone(self.find_visual_item(window, "programVersion"))
            self.assertEqual(window.findChild(QObject, "programVersion").property("text"), "v. " + VERSION)
            window.hide()

    def test_npsso_cancel_discards_draft_done_confirms_and_settings_save_persists(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            save_token = stack.enter_context(patch("qml_app.save_npsso"))
            stack.enter_context(patch("qml_app.save_configuration"))
            stack.enter_context(patch("qml_app.set_autostart_enabled"))
            restart = stack.enter_context(patch.object(controller, "restart"))
            original_status = controller.npssoMessage
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            clipboard = self.app.clipboard()
            original_clipboard = clipboard.text()
            stack.callback(clipboard.setText, original_clipboard)

            def click(name):
                button = self.find_visual_item(window, name)
                QTest.mouseClick(window, Qt.LeftButton,
                    pos=button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
                QTest.qWait(180)

            def open_and_paste(token, expires):
                window.setProperty("npssoVisible", True)
                QTest.qWait(180)
                clipboard.setText(json.dumps({"npsso": token, "expires_in": expires}))
                click("pasteNpssoButton")

            open_and_paste("test-discarded-token", 123)
            click("cancelNpssoButton")
            self.assertFalse(window.property("npssoVisible"))
            self.assertEqual(controller._pending_npsso, "")
            self.assertIsNone(controller._pending_expires_in)
            self.assertEqual(controller.npssoMessage, original_status)
            save_token.assert_not_called()
            restart.assert_not_called()

            open_and_paste("test-confirmed-token", 456)
            click("confirmNpssoButton")
            self.assertFalse(window.property("npssoVisible"))
            self.assertEqual(controller._pending_npsso, "test-confirmed-token")
            self.assertEqual(controller._pending_expires_in, 456)
            confirmed_status = controller.npssoMessage
            self.assertIn("готов к сохранению", confirmed_status)
            save_token.assert_not_called()
            restart.assert_not_called()

            open_and_paste("test-replacement-token", 789)
            click("cancelNpssoButton")
            self.assertEqual(controller._pending_npsso, "test-confirmed-token")
            self.assertEqual(controller._pending_expires_in, 456)
            self.assertEqual(controller.npssoMessage, confirmed_status)

            open_and_paste("test-escape-token", 999)
            QTest.keyClick(window, Qt.Key_Escape)
            QTest.qWait(200)
            self.assertFalse(window.property("npssoVisible"))
            self.assertEqual(controller._pending_npsso, "test-confirmed-token")
            self.assertEqual(controller._pending_expires_in, 456)
            save_token.assert_not_called()
            self.assertTrue(controller.saveSettings("123", 30, "cover", False))
            save_token.assert_called_once_with("test-confirmed-token", 456)
            restart.assert_called_once()
            self.assertEqual(controller._pending_npsso, "")
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_toolbar_buttons_are_compact_and_fit_both_languages_without_moving(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            buttons = [self.find_visual_item(window, name) for name in
                       ("settingsToolbarButton", "openStatisticsButton", "openAboutButton")]
            geometry = [(button.x(), button.y(), button.width(), button.height()) for button in buttons]
            for previous, current in zip(buttons, buttons[1:]):
                self.assertEqual(current.x() - previous.x() - previous.width(), 2)
            for language in ("ru", "en", "ru"):
                controller._language = language
                controller.language_changed.emit()
                QTest.qWait(40)
                self.assertEqual([(b.x(), b.y(), b.width(), b.height()) for b in buttons], geometry)
                for button in buttons:
                    self.assertEqual(button.property("leftPadding"), 4)
                    self.assertEqual(button.property("rightPadding"), 4)
                    label = next(child for child in button.childItems()
                                 if child.property("text") == button.property("text"))
                    metrics = QFontMetricsF(label.property("font"))
                    self.assertLessEqual(metrics.horizontalAdvance(button.property("text")), label.width())
                    widest = max(metrics.horizontalAdvance(button.property("russianText")),
                                 metrics.horizontalAdvance(button.property("englishText")))
                    self.assertAlmostEqual(button.width(), widest + 8, delta=1)
                    self.assertEqual(button.height(), 26)
            window.hide()

    def test_theme_buttons_place_botanical_immediately_after_oled(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            themes = window.property("themes").toVariant()
            self.assertEqual([theme["id"] for theme in themes],
                             ["light", "oled", "botanical", "terracotta", "indigo", "sakura", "aurora", "newyear"])
            self.assertEqual(window.property("currentThemeIndex"), 2)
            previous_x = -1
            for index, expected in enumerate(("light", "oled", "botanical")):
                button = self.find_visual_item(window, "themeHitTarget" + str(index))
                point = button.mapToScene(QPointF(button.width()/2, button.height()/2))
                self.assertGreater(point.x(), previous_x)
                previous_x = point.x()
                QTest.mouseClick(window, Qt.LeftButton, pos=point.toPoint())
                self.app.processEvents()
                self.assertEqual(controller.themeId, expected)
                self.assertEqual(window.property("currentThemeIndex"), index)
            window.hide()

    def test_pacman_forehead_is_wider_and_symmetric_in_all_frames(self):
        animation = TransparentGif()
        animation.setWidth(167)
        animation.setHeight(167 * 96 / 636)
        animation.sourceClipRect = QRectF(0, 130, 636, 96)
        animation.source = QUrl.fromLocalFile(str(QML_FILE.parent.parent / "assets" / "about-pacman.gif"))
        for frame in range(animation.frameCount):
            animation.roundedCapRect = QRectF()
            animation._movie.jumpToFrame(frame)
            animation._refresh_frame()
            original = animation._frame.copy()
            def yellow(image, x, y):
                color = image.pixelColor(x, y)
                return color.alpha() >= 200 and color.red() >= 200 and color.green() >= 170 and color.blue() < 100
            top = next(y for y in range(4, 11) if any(yellow(original, x, y) for x in range(63, 82)))
            old = [x for x in range(63, 82) if yellow(original, x, top)]
            animation.roundedCapRect = QRectF(240, 148, 68, 20)
            improved = animation._frame
            new = [x for x in range(63, 82) if yellow(improved, x, top)]
            self.assertGreater(len(new), len(old), frame)
            self.assertEqual(improved.pixelColor(min(old)-1, top), improved.pixelColor(max(old)+1, top))
            self.assertEqual(original.copy(0, 0, 60, original.height()), improved.copy(0, 0, 60, improved.height()))
            self.assertEqual(original.copy(63, 10, 19, 15), improved.copy(63, 10, 19, 15))
            self.assertEqual(improved.pixelColor(0, 0).alpha(), 0)

    def test_connection_indicator_stays_right_and_animates_by_psn_state(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            indicator = self.find_visual_item(window, "presenceStatusIndicator")
            dot = self.find_visual_item(window, "connectionIndicatorDot")
            label = self.find_visual_item(window, "presenceStatus")
            position = indicator.mapToScene(QPointF(indicator.width()/2, indicator.height()/2))
            self.assertEqual(controller.psnConnectionState, "connecting")
            self.assertTrue(indicator.property("animating"))
            self.assertEqual(indicator.property("pulseDuration"), 1100)
            pulse = indicator.property("pulse")
            QTest.qWait(160)
            self.assertNotEqual(indicator.property("pulse"), pulse)
            self.assertLess(dot.opacity(), 1)
            states = {
                BridgePhase.STARTING: "connecting", BridgePhase.WAITING_FOR_PSN: "connecting",
                BridgePhase.WAITING_FOR_DISCORD: "online", BridgePhase.WATCHING: "online",
                BridgePhase.ACTIVE: "online", BridgePhase.IDLE: "online", BridgePhase.STOPPED: "offline",
            }
            for phase, state in states.items():
                controller.set_snapshot(BridgeSnapshot(phase, "test", "Player",
                    GAME if phase == BridgePhase.ACTIVE else None))
                for language in ("en", "ru"):
                    controller._language = language
                    controller.language_changed.emit()
                    QTest.qWait(30)
                    self.assertEqual(controller.psnConnectionState, state)
                    self.assertEqual(indicator.property("mode"), state)
                    self.assertEqual(indicator.property("animating"), state != "offline")
                    self.assertEqual(indicator.property("pulseDuration"), 1100 if state == "connecting" else 3600)
                    current = indicator.mapToScene(QPointF(indicator.width()/2, indicator.height()/2))
                    self.assertAlmostEqual(current.x(), position.x())
                    self.assertAlmostEqual(current.y(), position.y())
                    visual_text_center = label.mapToScene(QPointF(0, label.property("baselineOffset")
                        - QFontMetricsF(label.property("font")).capHeight()/2)).y()
                    self.assertAlmostEqual(current.y(), visual_text_center, delta=0.51)
                    self.assertLess(label.mapToScene(QPointF(label.width(), 0)).x(),
                                    indicator.mapToScene(QPointF(0, 0)).x())
                    if state == "online":
                        self.assertGreaterEqual(dot.opacity(), 0.82)
                        self.assertLessEqual(dot.scale(), 1.03)
            with patch("qml_app.load_settings", side_effect=ValueError("missing configuration")):
                controller.start()
            self.app.processEvents()
            self.assertEqual(controller.psnConnectionState, "offline")
            self.assertFalse(indicator.property("animating"))
            controller.set_snapshot(BridgeSnapshot(BridgePhase.WAITING_FOR_PSN, "retrying"))
            self.app.processEvents()
            self.assertTrue(indicator.property("animating"))
            window.hide()
            self.app.processEvents()
            self.assertFalse(indicator.property("animating"))
            self.assertEqual(indicator.property("pulse"), 0)
            window.show()
            QTest.qWait(100)
            self.assertTrue(indicator.property("animating"))
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_startup_screen_closes_for_quick_window_without_waiting_for_psn(self):
        from startup_screen import StartupScreen
        from PySide6.QtGui import QIcon
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.WAITING_FOR_PSN, "Connection unavailable"))
            window.hide()
            splash = StartupScreen(QIcon(), language="en")
            try:
                splash.set_stage("Открытие главного окна…", 1)
                self.assertEqual(splash._status, "Opening main window…")
                splash.show()
                self.app.processEvents()
                self.assertTrue(splash.isVisible())
                # The old finish(window) takes a QWidget, not this QQuickWindow.
                with patch.object(splash, "finish", side_effect=AssertionError("QWidget-only finish must not be used")):
                    show_main_window(window, splash)
                    self.app.processEvents()
                    self.assertTrue(window.isVisible())
                    self.assertFalse(splash.isVisible())
                    self.assertEqual(controller.phase, "Ожидание PSN")
                    # Restoring from the tray must not bring the startup screen back.
                    window.hide()
                    show_main_window(window, splash)
                    self.assertTrue(window.isVisible())
                    self.assertFalse(splash.isVisible())
                    window.hide()
                    show_main_window(window)
                    self.assertTrue(window.isVisible())
            finally:
                splash.close()
                window.hide()

    def test_interactive_startup_dismisses_splash_when_psn_never_connects(self):
        project = Path(__file__).resolve().parents[1]
        script = '''
from contextlib import ExitStack
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSplashScreen
import qml_app
from settings_store import StoredConfiguration

def verify():
    app = QApplication.instance()
    main_visible = any(w.title() == "PS3 Presence" and w.isVisible() for w in app.topLevelWindows())
    splash_visible = any(isinstance(w, QSplashScreen) and w.isVisible() for w in app.topLevelWidgets())
    print(f"main_visible={main_visible}, splash_visible={splash_visible}", flush=True)
    app.exit(0 if main_visible and not splash_visible else 3)

def offline_start(controller):
    controller._phase = "Ожидание PSN"
    controller.changed.emit()
    QTimer.singleShot(1100, verify)

with ExitStack() as stack:
    stack.enter_context(patch("qml_app.load_configuration", return_value=StoredConfiguration()))
    stack.enter_context(patch("qml_app.load_npsso", return_value=None))
    stack.enter_context(patch("qml_app.load_npsso_expires_at", return_value=None))
    stack.enter_context(patch("qml_app.load_local_cover_index", return_value={}))
    stack.enter_context(patch("qml_app.is_autostart_enabled", return_value=False))
    stack.enter_context(patch("qml_app.STATISTICS_FILE", None))
    stack.enter_context(patch.object(qml_app.PresenceController, "start", offline_start))
    raise SystemExit(qml_app.main(["--software-rendering"]))
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=project,
                                capture_output=True, text=True, timeout=15,
                                env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("main_visible=True, splash_visible=False", result.stdout)
        self.assertNotIn("TypeError", result.stderr)

    def test_about_button_opens_centered_dialog_and_plays_gif_only_while_open(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            button = self.find_visual_item(window, "openAboutButton")
            animation = window.findChild(QObject, "aboutAnimation")
            dialog = window.findChild(QObject, "aboutDialog")
            self.assertFalse(window.property("aboutVisible"))
            self.assertEqual(animation.property("source").toString(), "")
            point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(200)
            self.assertTrue(window.property("aboutVisible"))
            self.assertTrue(dialog.property("visible"))
            self.assertTrue(animation.property("imageReady"))
            self.assertAlmostEqual(animation.width(), (dialog.property("width") - 32)/2, delta=1)
            self.assertAlmostEqual(animation.height(), animation.width()*96/636, delta=1)
            self.assertEqual(animation._frame.pixelColor(0, 0).alpha(), 0)
            self.assertTrue(any(animation._frame.pixelColor(x, y).alpha() > 0
                                for y in range(animation._frame.height())
                                for x in range(animation._frame.width())))
            self.assertGreater(animation.property("frameCount"), 1)
            frames = set()
            for _ in range(8):
                frames.add(animation.property("currentFrame"))
                QTest.qWait(180)
            self.assertGreater(len(frames), 1)
            for theme in ("light", "oled", "aurora"):
                controller.saveTheme(theme)
                self.app.processEvents()
                self.assertAlmostEqual(dialog.property("x"), (window.width() - dialog.property("width"))/2, delta=1)
                self.assertAlmostEqual(dialog.property("y"), (window.height() - dialog.property("height"))/2, delta=1)
            close = self.find_visual_item(window, "closeAboutButton")
            point = close.mapToScene(QPointF(close.width()/2, close.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(200)
            self.assertFalse(window.property("aboutVisible"))
            self.assertFalse(animation.property("playing"))
            self.assertEqual(animation.property("source").toString(), "")
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_about_sun_phrase_falls_holds_scatters_and_stops_when_hidden(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            phrase = window.findChild(QObject, "aboutSunPraise")
            self.assertFalse(phrase.property("active"))
            self.assertFalse(phrase.property("animating"))
            window.setProperty("aboutVisible", True)
            QTest.qWait(220)
            self.assertTrue(phrase.property("animating"))
            self.assertGreater(phrase.property("elapsed"), 0)
            window.hide()
            self.app.processEvents()
            self.assertFalse(phrase.property("animating"))
            self.assertEqual(phrase.property("elapsed"), 0)
            window.show()
            QTest.qWait(100)
            self.assertTrue(phrase.property("animating"))
            window.setProperty("aboutVisible", False)
            QTest.qWait(200)
            self.assertFalse(phrase.property("animating"))
            self.assertEqual(phrase.property("elapsed"), 0)
            window.setProperty("aboutVisible", True)
            QTest.qWait(200)
            self.assertTrue(phrase.property("animating"))

            # Pause the native clock and inspect repeatable points in its cycle.
            phrase.setProperty("active", False)
            letters = [self.find_visual_item(window, "sunPraiseLetter" + str(index))
                       for index in range(phrase.property("letterCount"))]
            self.assertEqual("".join(letter.property("text") for letter in letters), "Praise Teh Sun \\[T]/")
            self.assertGreater(len({round(letter.property("fallDelay")) for letter in letters}), 8)
            self.assertGreater(len({round(letter.property("fallDuration")) for letter in letters}), 8)
            phrase.setProperty("elapsed", 600)
            self.assertEqual(phrase.property("phase"), "falling")
            self.assertTrue(any(letter.opacity() == 0 for letter in letters))
            self.assertTrue(any(letter.opacity() > 0 and letter.y() < letter.property("homeY") for letter in letters))
            phrase.setProperty("elapsed", 2400)
            self.assertEqual(phrase.property("phase"), "assembled")
            for letter in letters:
                self.assertAlmostEqual(letter.x(), letter.property("homeX"))
                self.assertAlmostEqual(letter.y(), letter.property("homeY"))
                self.assertEqual(letter.opacity(), 1)
                self.assertEqual(letter.rotation(), 0)
            positions = [(letter.x(), letter.y()) for letter in letters]
            phrase.setProperty("elapsed", 5600)
            self.assertEqual([(letter.x(), letter.y()) for letter in letters], positions)
            phrase.setProperty("elapsed", 6800)
            self.assertEqual(phrase.property("phase"), "scattering")
            self.assertTrue(any(letter.y() > letter.property("homeY") + 10 for letter in letters))
            self.assertTrue(any(letter.opacity() < 1 for letter in letters))
            phrase.setProperty("elapsed", 8100)
            self.assertEqual(phrase.property("phase"), "waiting")
            self.assertTrue(all(letter.opacity() == 0 for letter in letters))
            old_delays = [letter.property("fallDelay") for letter in letters]
            phrase.setProperty("cycle", 1)
            self.assertNotEqual([letter.property("fallDelay") for letter in letters], old_delays)
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_clicking_sun_phrase_bursts_in_all_directions_then_resumes_old_cycle(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            window.setProperty("aboutVisible", True)
            QTest.qWait(200)
            phrase = self.find_visual_item(window, "aboutSunPraise")
            timeline = window.findChild(QObject, "sunPraiseTimeline")
            animation = window.findChild(QObject, "sunPraiseBurstAnimation")
            timeline.setProperty("paused", True)
            phrase.setProperty("elapsed", 2400)
            letters = [self.find_visual_item(window, "sunPraiseLetter" + str(i))
                       for i in range(phrase.property("letterCount"))]
            positions = [(letter.x(), letter.y()) for letter in letters]
            point = phrase.mapToScene(QPointF(phrase.width()/2, phrase.height()/2)).toPoint()
            with patch.object(controller, "openAuthorDiscord") as profile, patch.object(controller, "copyAuthorDiscordUsername") as copy:
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertTrue(phrase.property("bursting"))
                self.assertEqual(phrase.property("phase"), "bursting")
                self.assertTrue(timeline.property("paused"))
                self.assertEqual([(letter.property("burstX"), letter.property("burstY")) for letter in letters], positions)
                animation.setProperty("paused", True)
                phrase.setProperty("burstElapsed", 300)
                dx = [letter.x() - x for letter, (x, y) in zip(letters, positions)]
                dy = [letter.y() - y for letter, (x, y) in zip(letters, positions)]
                self.assertLess(min(dx), -10)
                self.assertGreater(max(dx), 10)
                self.assertLess(min(dy), -10)
                self.assertGreater(max(dy), 10)
                self.assertTrue(all(0 < letter.opacity() < 1 for letter in letters))
                self.assertTrue(any(abs(letter.rotation()) > 10 for letter in letters))
                profile.assert_not_called()
                copy.assert_not_called()
            animation.setProperty("paused", False)
            QTest.qWait(1000)
            self.assertFalse(phrase.property("bursting"))
            self.assertEqual(phrase.property("cycle"), 1)
            self.assertTrue(timeline.property("running"))
            self.assertFalse(timeline.property("paused"))
            self.assertEqual(phrase.property("phase"), "falling")
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertTrue(phrase.property("bursting"))
            window.setProperty("aboutVisible", False)
            QTest.qWait(200)
            self.assertFalse(phrase.property("animating"))
            self.assertFalse(phrase.property("bursting"))
            self.assertEqual(phrase.property("elapsed"), 0)
            self.assertEqual(phrase.property("burstElapsed"), 0)
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_about_author_discord_link_copies_username_and_opens_profile(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            window.setProperty("aboutVisible", True)
            QTest.qWait(200)
            dialog = window.findChild(QObject, "aboutDialog")
            nickname = self.find_visual_item(window, "authorDiscordUsername")
            feedback = self.find_visual_item(window, "authorDiscordFeedback")
            self.assertEqual(nickname.property("text"), "lapamivverh")
            praise = self.find_visual_item(window, "aboutSunPraise")
            self.assertEqual(praise.property("text"), "Praise Teh Sun \\[T]/")
            self.assertGreater(praise.mapToScene(QPointF(0, 0)).x(),
                               nickname.mapToScene(QPointF(nickname.width(), 0)).x())
            self.assertLessEqual(praise.x() + praise.width(), praise.parentItem().width())
            self.assertIsNone(self.find_visual_item(window, "copyAuthorDiscordButton"))
            self.assertIsNone(self.find_visual_item(window, "openAuthorDiscordButton"))
            self.assertEqual(self.find_visual_item(window, "programVersion").y(), 0)
            logo = self.find_visual_item(window, "authorDiscordLogo")
            for theme, filename in (("light", "discord-mark-black.svg"), ("oled", "discord-mark-white.svg"), ("aurora", "discord-mark-white.svg")):
                controller.saveTheme(theme)
                QTest.qWait(30)
                self.assertTrue(logo.property("imageReady"))
                self.assertTrue(logo.property("source").toString().endswith(filename))
                self.assertEqual((logo.width(), logo.height()), (16, 16))
                face = self.find_visual_item(window, "authorDiscordLogoFace")
                shadow = self.find_visual_item(window, "authorDiscordLogoShadow")
                self.assertEqual((face.width(), face.height()), (16, 12))
                self.assertEqual(face.property("sourceSize").width(), 160)
                self.assertTrue(face.property("mipmap"))
                self.assertGreater(shadow.y(), face.y())
                self.assertLessEqual(shadow.opacity(), 0.3)
                self.assertLess(logo.mapToScene(QPointF(logo.width(), 0)).x(),
                                nickname.mapToScene(QPointF(0, 0)).x())
                self.assertAlmostEqual(nickname.mapToScene(QPointF(0, 0)).x()
                                       - logo.mapToScene(QPointF(logo.width(), 0)).x(), 6)
                self.assertAlmostEqual(logo.mapToScene(QPointF(0, logo.height()/2)).y()
                                       - nickname.mapToScene(QPointF(0, nickname.height()/2)).y(), 1)

            def click(item):
                point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.app.processEvents()

            previous_clipboard = self.app.clipboard().text()
            try:
                with patch("qml_app.sys.platform", "win32"), patch("qml_app.os.startfile", create=True) as startfile, patch("qml_app.QDesktopServices.openUrl") as open_url:
                    click(nickname)
                    startfile.assert_called_once_with("discord://-/users/308300626062737411")
                    open_url.assert_not_called()
                    self.assertEqual(self.app.clipboard().text(), "lapamivverh")
                    self.assertEqual(feedback.property("text"), "Ник скопирован")
                    self.assertTrue(feedback.property("visible"))
                    self.assertFalse(dialog.property("profileOpenFailed"))
                QTest.qWait(1900)
                self.assertFalse(feedback.property("visible"))
                self.assertEqual(nickname.property("text"), "lapamivverh")
                controller._language = "en"
                controller.language_changed.emit()
                self.app.processEvents()
                with patch("qml_app.sys.platform", "win32"), patch("qml_app.os.startfile", create=True, side_effect=OSError), patch("qml_app.QDesktopServices.openUrl", return_value=True) as open_url:
                    click(nickname)
                    self.assertEqual([call.args[0].toString() for call in open_url.call_args_list],
                                     ["https://discord.com/users/308300626062737411"])
                    self.assertEqual(self.app.clipboard().text(), "lapamivverh")
                    self.assertEqual(feedback.property("text"), "Username copied")
                    self.assertFalse(dialog.property("profileOpenFailed"))
                with patch("qml_app.sys.platform", "linux"), patch("qml_app.QDesktopServices.openUrl", return_value=False):
                    self.app.clipboard().setText("previous value")
                    click(nickname)
                    self.assertEqual(self.app.clipboard().text(), "lapamivverh")
                    self.assertTrue(feedback.property("visible"))
                    self.assertTrue(feedback.property("text").startswith("Could not open"))
                    animation = self.find_visual_item(window, "aboutAnimation")
                    self.assertLessEqual(feedback.mapToScene(QPointF(0, feedback.height())).y(),
                                         animation.mapToScene(QPointF(0, 0)).y())
            finally:
                self.app.clipboard().setText(previous_clipboard)
            click(self.find_visual_item(window, "closeAboutButton"))
            QTest.qWait(200)
            self.assertFalse(dialog.property("usernameCopied"))
            self.assertFalse(dialog.property("profileOpenFailed"))
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_about_github_links_open_correct_pages_in_both_languages_and_all_themes(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            window.setProperty("aboutVisible", True)
            QTest.qWait(200)
            logo = self.find_visual_item(window, "aboutGitHubLogo")
            discord_logo = self.find_visual_item(window, "authorDiscordLogo")
            repository = self.find_visual_item(window, "aboutGitHubRepository")
            issues = self.find_visual_item(window, "aboutGitHubIssues")
            feedback = self.find_visual_item(window, "aboutWebLinkFeedback")
            animation = self.find_visual_item(window, "aboutAnimation")
            dialog = window.findChild(QObject, "aboutDialog")
            controller.toggleNewYearThemeButton()
            self.assertEqual(repository.property("text"), "PS3Presence")
            for theme in ("light", "oled", "botanical", "terracotta", "indigo", "sakura", "aurora", "newyear"):
                controller.saveTheme(theme)
                QTest.qWait(30)
                self.assertTrue(logo.property("imageReady"))
                filename = "github-mark-black.svg" if theme == "light" else "github-mark-white.svg"
                self.assertTrue(logo.property("source").toString().endswith(filename))
                self.assertEqual((logo.width(), logo.height()), (discord_logo.width(), discord_logo.height()))
                self.assertEqual(logo.property("sourceSize").width(), 160)
                self.assertTrue(logo.property("mipmap"))
                self.assertAlmostEqual(repository.mapToScene(QPointF()).x()
                                       - logo.mapToScene(QPointF(logo.width(), 0)).x(), 6)
                self.assertAlmostEqual(animation.mapToScene(QPointF()).x(), issues.mapToScene(QPointF()).x())
                self.assertAlmostEqual(animation.mapToScene(QPointF()).y()
                                       - issues.mapToScene(QPointF(0, issues.height())).y(), 8)
                self.assertEqual(issues.property("font").pixelSize(), 10)
                self.assertEqual(issues.height(), 20)
                self.assertAlmostEqual(logo.mapToScene(QPointF(0, logo.height()/2)).y(),
                                       repository.mapToScene(QPointF(0, repository.height()/2)).y())

            def click(item):
                point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.app.processEvents()

            for language, caption in (("ru", "Сообщить о проблеме"), ("en", "Report an issue")):
                controller._language = language
                controller.language_changed.emit()
                self.app.processEvents()
                self.assertEqual(issues.property("text"), caption)
                self.assertLessEqual(issues.x() + issues.width(), issues.parentItem().width())
                clipboard = self.app.clipboard().text()
                with patch("qml_app.QDesktopServices.openUrl", return_value=True) as open_url:
                    click(repository)
                    click(issues)
                    self.assertEqual([call.args[0].toString() for call in open_url.call_args_list], [
                        "https://github.com/forrestdarko-commits/PS3Presence",
                        "https://github.com/forrestdarko-commits/PS3Presence/issues",
                    ])
                    self.assertFalse(feedback.property("visible"))
                    self.assertEqual(self.app.clipboard().text(), clipboard)
                with patch("qml_app.QDesktopServices.openUrl", return_value=False):
                    click(issues)
                    self.assertTrue(feedback.property("visible"))
                # Both failure notices leave the bottom link and animation clear.
                dialog.setProperty("profileOpenFailed", True)
                self.app.processEvents()
                self.assertLessEqual(feedback.mapToScene(QPointF(0, feedback.height())).y(),
                                     issues.mapToScene(QPointF()).y())
                dialog.setProperty("profileOpenFailed", False)
                with patch("qml_app.QDesktopServices.openUrl", return_value=True):
                    click(repository)
                    self.assertFalse(feedback.property("visible"))
            with patch("qml_app.QDesktopServices.openUrl", return_value=False):
                click(repository)
            click(self.find_visual_item(window, "closeAboutButton"))
            QTest.qWait(200)
            self.assertFalse(dialog.property("webOpenFailed"))
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_language_buttons_translate_all_dialogs_dates_and_status_without_resetting_state(self):
        import re
        with ExitStack() as stack, tempfile.TemporaryDirectory() as folder:
            stack.enter_context(patch.object(settings_store, "CONFIG_FILE", Path(folder)/"config.json"))
            settings_store.save_configuration(StoredConfiguration("123", 45, "cover", theme_id="aurora"))
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            controller._statistics = GameTimeTracker(None, clock=lambda: 100, wall_clock=lambda: datetime(2026, 10, 6).timestamp())
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", GAME,
                discord_connected=True, refresh_token_expires_at=datetime.now().timestamp()+90061))
            model = controller.gameStatistics
            resets = []
            model.modelReset.connect(lambda: resets.append(True))

            def click(name):
                item = self.find_visual_item(window, name)
                QTest.mouseClick(window, Qt.LeftButton,
                    pos=item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint())
                QTest.qWait(80)

            reconnect = self.find_visual_item(window, "reconnectDiscordButton")
            reconnect_geometry = (reconnect.x(), reconnect.y(), reconnect.width(), reconnect.height())
            self.assertEqual(reconnect.width(), 175)
            click("enLanguageButton")
            self.assertEqual((reconnect.x(), reconnect.y(), reconnect.width(), reconnect.height()), reconnect_geometry)
            self.assertEqual(controller.language, "en")
            self.assertEqual(window.title(), "PS3 Presence")
            self.assertEqual(settings_store.load_configuration().language, "en")
            self.assertEqual(self.find_visual_item(window, "settingsToolbarButton").property("text"), "Settings")
            self.assertEqual(controller.phase, "Game displayed")
            self.assertEqual(controller.discord, "Connected")
            self.assertIn("day", controller.auth)
            self.assertIn("October", controller.statisticsSince)
            self.assertIn("October", model._rows[0]["lastPlayed"])
            self.assertIn("October", controller.sessionHistory._rows[0]["startedAt"])
            self.assertEqual(controller.sessionHistory._rows[0]["state"], "Currently playing")
            self.assertFalse(resets)
            self.assertEqual(settings_store.load_configuration().poll_interval, 45)
            stored = settings_store.load_configuration()
            with patch("qml_app.set_autostart_enabled"), patch.object(controller, "restart"), patch("qml_app.load_configuration", return_value=stored):
                self.assertTrue(controller.saveSettings("123", 45, "cover", False))
            self.assertEqual(settings_store.load_configuration().language, "en")

            def visible_text_is_english(item):
                if item.isVisible():
                    value = item.property("text")
                    if isinstance(value, str):
                        self.assertIsNone(re.search("[А-Яа-яЁё]", value), (item.objectName(), value))
                for child in item.childItems():
                    visible_text_is_english(child)

            for prop in ("aboutVisible", "settingsVisible", "npssoVisible", "statisticsVisible"):
                window.setProperty(prop, True)
                QTest.qWait(100)
                visible_text_is_english(window.contentItem())
                if prop == "aboutVisible":
                    version = self.find_visual_item(window, "programVersion")
                    animation = self.find_visual_item(window, "aboutAnimation")
                    self.assertEqual(version.property("text"), "v. " + VERSION)
                    self.assertEqual(animation.x(), 0)
                    self.assertAlmostEqual(animation.y()+animation.height(), animation.parentItem().height(), delta=.1)
                window.setProperty(prop, False)
                QTest.qWait(80)
            click("ruLanguageButton")
            self.assertEqual((reconnect.x(), reconnect.y(), reconnect.width(), reconnect.height()), reconnect_geometry)
            self.assertEqual(controller.language, "ru")
            self.assertEqual(controller.phase, "Игра отображается")
            self.assertIn("октября", controller.statisticsSince)
            self.assertEqual(self.find_visual_item(window, "settingsToolbarButton").property("text"), "Настройки")
            self.assertFalse(resets)
            window.setProperty("decorationsEnabled", True)
            lamp = self.find_visual_item(window, "garlandLamp0")
            lamp.setProperty("lit", True)
            controller.saveLanguage("en")
            self.assertTrue(lamp.property("lit"))
            self.assertTrue(window.property("decorationsEnabled"))
            with patch("qml_app.save_language", side_effect=OSError("test write failure")):
                controller.saveLanguage("ru")
                self.assertEqual(controller.language, "en")
                self.assertIn("Could not save language", controller.logs)
            click("ruLanguageButton")
            self.assertEqual(controller.language, "ru")
            click("enLanguageButton")
            self.assertEqual(controller.language, "en")
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_psn_avatar_and_nickname_update_without_recreating_card(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            image = QImage(64, 64, QImage.Format_ARGB32)
            image.fill(QColor("#d47759"))
            image_path = Path(directory) / "avatar.png"
            self.assertTrue(image.save(str(image_path)))
            avatar_url = QUrl.fromLocalFile(str(image_path)).toString()
            controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "idle", "ExampleUser", avatar_url=avatar_url))
            QTest.qWait(200)
            avatar = self.find_visual_item(window, "psnAvatar")
            nickname = self.find_visual_item(window, "psnNickname")
            self.assertEqual(nickname.property("text"), "ExampleUser")
            self.assertTrue(avatar.property("imageReady"))
            self.assertEqual(controller.avatar, avatar_url)
            controller.changed.emit()  # Includes the once-per-second auth countdown.
            self.app.processEvents()
            self.assertIs(self.find_visual_item(window, "psnAvatar"), avatar)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "idle", "OtherUser"))
            self.app.processEvents()
            self.assertFalse(avatar.property("imageReady"))
            self.assertEqual(avatar.property("initials"), "O")
            self.assertEqual(controller.avatar, "")
            window.hide()

    def test_event_log_context_menu_is_compact_useful_and_themed(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            controller.append_log("First event")
            controller.append_log("Second event")
            self.app.processEvents()
            event_log = self.find_visual_item(window, "eventLogTextArea")
            point = event_log.mapToScene(QPointF(80, 30)).toPoint()

            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora"):
                controller.saveTheme(theme)
                self.app.processEvents()
                QTest.mouseClick(window, Qt.RightButton, pos=point)
                QTest.qWait(40)
                menu = window.findChild(QObject, "eventLogContextMenu")
                background = window.findChild(QObject, "eventLogContextMenuBackground")
                self.assertIsNotNone(menu)
                self.assertTrue(menu.property("visible"), theme)
                self.assertEqual(menu.property("count"), 3)
                self.assertLessEqual(menu.property("width"), 178)
                self.assertLessEqual(menu.property("height"), 100)
                palette = window.property("theme").toVariant()
                self.assertEqual(background.property("color").name(), palette["dialog"], theme)
                self.assertEqual(background.property("outlineColor").name(), palette["border"], theme)
                self.assertEqual(window.findChild(QObject, "eventLogCopySelection").property("text"), "Копировать")
                self.assertEqual(window.findChild(QObject, "eventLogCopyAll").property("text"), "Копировать весь лог")
                self.assertEqual(window.findChild(QObject, "eventLogSelectAll").property("text"), "Выделить всё")
                QTest.keyClick(window, Qt.Key_Escape)
                self.app.processEvents()
                self.assertFalse(menu.property("visible"), theme)
            window.hide()

    def test_event_log_adds_a_timestamp_to_each_entry(self):
        with ExitStack() as stack, patch("qml_app.datetime") as clock:
            controller, engine, window = self.create_window(stack)
            clock.now.return_value = datetime(2026, 9, 21, 14, 5, 9)
            controller.append_log("Discord RPC connected.")
            self.assertEqual(controller.logs, "[14:05:09] Discord RPC connected.")
            window.hide()

    def test_idle_dualshock3_is_centred_and_replaced_by_ready_game_cover(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            tile = self.find_visual_item(window, "gameCoverTile")
            icon = self.find_visual_item(window, "gamepadPlaceholder")
            QTest.qWait(150)
            self.assertTrue(icon.property("imageReady"))
            self.assertTrue(icon.property("source").toString().endswith("dualshock3.png"))
            self.assertAlmostEqual(icon.x() + icon.width() / 2, tile.width() / 2, delta=.1)
            self.assertAlmostEqual(icon.y() + icon.height() / 2, tile.height() / 2, delta=.1)
            self.assertEqual((tile.width(), tile.height()), (76, 76))
            self.assertTrue(icon.isVisible())
            # Verify actual controller pixels, not just the placeholder flag.
            if self.app.platformName() == "windows":
                screenshot = window.grabWindow()
                graphite = []
                origin = icon.mapToScene(QPointF(0, 0)).toPoint()
                for y in range(origin.y(), origin.y() + round(icon.height())):
                    for x in range(origin.x(), origin.x() + round(icon.width())):
                        color = screenshot.pixelColor(x, y)
                        if max(color.red(), color.green(), color.blue()) - min(color.red(), color.green(), color.blue()) < 12:
                            graphite.append((x, y))
                self.assertGreater(len(graphite), 100)
                for axis in (0, 1):
                    center = (min(p[axis] for p in graphite) + max(p[axis] for p in graphite)) / 2
                    expected = tile.mapToScene(QPointF(38, 38))
                    self.assertAlmostEqual(center, expected.x() if axis == 0 else expected.y(), delta=2)
            cover = QImage(64, 64, QImage.Format_ARGB32)
            cover.fill(QColor("#2984cb"))
            path = Path(directory) / "cover.png"
            self.assertTrue(cover.save(str(path)))
            controller._cover = QUrl.fromLocalFile(str(path)).toString()
            controller.changed.emit()
            QTest.qWait(150)
            self.assertFalse(icon.isVisible())
            controller._cover = ""
            controller.changed.emit()
            self.app.processEvents()
            self.assertTrue(icon.isVisible())
            window.hide()

    def test_cannabis_art_is_transparent_and_exclusive_to_botanical_theme(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            controller.toggleNewYearThemeButton()
            for theme, filename in (("botanical", "botanical-cannabis-theme.png"), ("light", "botanical-theme.png"),
                                    ("aurora", "botanical-theme.png"), ("newyear", "newyear-theme.png")):
                controller.saveTheme(theme)
                self.app.processEvents()
                self.assertTrue(window.property("themeArtwork").toString().endswith(filename))
            art = QImage(str(QML_FILE.parent.parent / "assets" / "botanical-cannabis-theme.png"))
            self.assertEqual((art.width(), art.height()), (1536, 1024))
            self.assertTrue(art.hasAlphaChannel())
            self.assertEqual(art.pixelColor(768, 512).alpha(), 0)
            self.assertGreater(art.pixelColor(1483, 966).alpha(), 96)
            controller.saveTheme("botanical")
            self.app.processEvents()
            self.assertTrue(controller.isSecretLeafHit(1483 * 680 / 1536, 966 * 680 / 1536))
            self.assertFalse(controller.isSecretLeafHit(1416 * 680 / 1536, 1011 * 680 / 1536))
            window.hide()

    def test_local_cover_replaces_remote_images_in_main_and_previous_sessions(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            clock = Clock()
            controller._statistics = GameTimeTracker(None, clock=clock, wall_clock=clock.wall)
            public = "https://example.invalid/public-cover.jpg"
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", GAME, cover_url=public))
            clock.value += 5
            controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "idle", "Player"))
            image = QImage(64, 64, QImage.Format_ARGB32)
            image.fill(QColor("#258bd2"))
            path = Path(directory) / "cover.png"
            self.assertTrue(image.save(str(path)))
            local = QUrl.fromLocalFile(str(path)).toString()
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", GAME,
                cover_url=public, local_cover_url=local))
            self.assertEqual(controller.cover, local)
            self.assertEqual(controller._statistics.rows()[0]["coverUrl"], public)
            self.assertEqual(controller.gameStatistics._rows[0]["coverUrl"], local)
            self.assertEqual({row["coverUrl"] for row in controller.sessionHistory._rows}, {local})
            self.assertEqual(controller._statistics.rows()[0]["totalSeconds"], 5)
            self.assertEqual(controller._statistics.rows()[0]["sessionCount"], 2)
            QTest.qWait(100)
            # The QML item is visible only when Image.status is Ready; the
            # internal Qt enum itself is not convertible by PySide.
            self.assertTrue(self.find_visual_item(window, "currentGameCover").isVisible())
            window.close()

    def test_game_statistics_dialog_covers_live_timer_and_incremental_model(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            clock = Clock()
            controller._statistics = GameTimeTracker(None, clock=clock, wall_clock=clock.wall)
            picture = QImage(64, 64, QImage.Format_ARGB32)
            picture.fill(QColor("#258bd2"))
            path = Path(directory) / "cover.png"
            self.assertTrue(picture.save(str(path)))
            cover = QUrl.fromLocalFile(str(path)).toString()
            game = replace(GAME, title_icon_url=cover)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.WAITING_FOR_DISCORD, "RPC unavailable", "Player", game,
                game_started_at=int(clock.wall())-120))
            timer = self.find_visual_item(window, "currentGameTimer")
            self.assertTrue(timer.isVisible())
            self.assertEqual(timer.property("text"), "В игре · 00:02:00")
            button = self.find_visual_item(window, "openStatisticsButton")
            QTest.mouseClick(window, Qt.LeftButton, pos=button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
            QTest.qWait(220)
            self.assertTrue(window.property("statisticsVisible"))
            since = self.find_visual_item(window, "statisticsSince")
            self.assertTrue(since.isVisible())
            expected_since = "Статистика с " + format_russian_date(clock.wall())
            self.assertEqual(since.property("text"), expected_since)
            self.assertLessEqual(since.property("implicitWidth"), since.width())
            total = self.find_visual_item(window, "statisticsTotal")
            self.assertLessEqual(total.mapToScene(QPointF(0, total.height())).y(), since.mapToScene(QPointF(0, 0)).y())
            self.assertLessEqual(since.y() + since.height(), since.parentItem().height())
            model = controller.gameStatistics
            self.assertEqual(model.rowCount(), 1)
            cover_item = self.find_visual_item(window, "statisticsCover0")
            self.assertIsNotNone(cover_item)
            self.assertTrue(cover_item.property("imageReady"))
            point = cover_item.mapToScene(QPointF(cover_item.width()/2, cover_item.height()/2)).toPoint()
            color = window.grabWindow().pixelColor(point)
            self.assertGreater(color.blue(), color.green()+30)
            resets = []
            model.modelReset.connect(lambda: resets.append(True))
            for _ in range(4):
                clock.value += 1
                controller._refresh_auth()
                self.app.processEvents()
            self.assertEqual(timer.property("text"), "В игре · 00:02:04")
            self.assertEqual(controller.totalPlaytime, "00:00:04")
            self.assertEqual(since.property("text"), expected_since)
            self.assertFalse(resets)
            self.assertIs(self.find_visual_item(window, "statisticsCover0"), cover_item)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", replace(game, game_status="Mission"), game_started_at=int(clock.wall())-124))
            self.assertEqual(controller._statistics.rows()[0]["sessionCount"], 1)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", replace(OTHER, title_icon_url=cover)))
            self.assertEqual(model.rowCount(), 2)
            self.assertEqual(controller.sessionElapsed, "00:00:00")
            controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "idle", "Player"))
            self.app.processEvents()
            self.assertFalse(timer.isVisible())
            close = self.find_visual_item(window, "closeStatisticsButton")
            QTest.mouseClick(window, Qt.LeftButton, pos=close.mapToScene(QPointF(close.width()/2, close.height()/2)).toPoint())
            self.assertFalse(window.property("statisticsVisible"))
            window.hide()

    def test_settings_draft_survives_status_updates_and_interval_is_persisted(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            stack.enter_context(patch.object(settings_store, "CONFIG_FILE", Path(directory) / "config.json"))
            stack.enter_context(patch("qml_app.load_configuration", side_effect=settings_store.load_configuration))
            stack.enter_context(patch("qml_app.is_autostart_enabled", return_value=False))
            autostart = stack.enter_context(patch("qml_app.set_autostart_enabled"))
            restart = stack.enter_context(patch.object(controller, "restart"))
            settings_store.save_configuration(StoredConfiguration("1234567890", 30, "original", {"2": (4, 3)}, "aurora"))
            controller.open_settings_requested.connect(lambda: window.setProperty("settingsVisible", True))

            def click(name):
                item = self.find_visual_item(window, name)
                QTest.mouseClick(window, Qt.LeftButton,
                                pos=item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint())
                self.app.processEvents()

            for value in (45, 60, 120):
                controller.openSettings()
                QTest.qWait(100)
                field = self.find_visual_item(window, "settingsIntervalField")
                click("settingsIntervalField")
                QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
                for digit in str(value):
                    QTest.keyClick(window, getattr(Qt, "Key_" + digit))
                self.assertEqual(field.property("text"), str(value))
                image = self.find_visual_item(window, "settingsImageField")
                image.setProperty("text", "edited-cover")
                checkbox = self.find_visual_item(window, "settingsAutostartCheckBox")
                checkbox.setProperty("checked", True)
                for _ in range(3):
                    controller.changed.emit()
                    QTest.qWait(30)
                    self.assertEqual(field.property("text"), str(value))
                    self.assertEqual(image.property("text"), "edited-cover")
                    self.assertTrue(checkbox.property("checked"))
                click("saveSettingsButton")
                QTest.qWait(100)
                self.assertFalse(window.property("settingsVisible"))
                saved = settings_store.load_configuration()
                self.assertEqual(saved.poll_interval, value)
                self.assertEqual(saved.light_offsets, {"2": (4, 3)})
                self.assertEqual(saved.theme_id, "aurora")
                self.assertEqual(controller.settingsInterval, value)
                with patch("bridge.load_npsso", return_value="test"):
                    from bridge import load_settings
                    self.assertEqual(load_settings().poll_interval, value)
                controller.openSettings()
                QTest.qWait(100)
                self.assertEqual(field.property("text"), str(value))
                field.setProperty("text", "99")
                window.setProperty("settingsVisible", False)
                QTest.qWait(100)
                self.assertEqual(settings_store.load_configuration().poll_interval, value)
            self.assertEqual(restart.call_count, 3)
            self.assertEqual(autostart.call_count, 3)
            # Invalid input must not silently close the dialog or modify settings.
            controller.openSettings()
            QTest.qWait(100)
            field.setProperty("text", "10")
            click("saveSettingsButton")
            QTest.qWait(100)
            self.assertTrue(window.property("settingsVisible"))
            self.assertIn("15", controller.settingsError)
            self.assertEqual(field.property("text"), "10")
            self.assertEqual(settings_store.load_configuration().poll_interval, 120)
            autostart.assert_called_with(True)
            self.assertEqual(autostart.call_count, 3)
            with patch("qml_app.save_configuration", side_effect=OSError("Test write failure")):
                field.setProperty("text", "90")
                click("saveSettingsButton")
                QTest.qWait(100)
                self.assertTrue(window.property("settingsVisible"))
                self.assertEqual(controller.settingsError, "Test write failure")
                self.assertEqual(field.property("text"), "90")
                self.assertEqual(settings_store.load_configuration().poll_interval, 120)
            window.hide()

    def test_session_history_tabs_covers_live_updates_and_theme_geometry(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            clock = Clock()
            clock.wall = lambda: datetime(2026, 9, 13, 20, 2, 27).timestamp() + clock.value
            controller._statistics = GameTimeTracker(None, clock=clock, wall_clock=clock.wall)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(message) for message in messages))
            window.setProperty("statisticsVisible", True)
            QTest.qWait(80)

            def click(name):
                button = self.find_visual_item(window, name)
                QTest.mouseClick(window, Qt.LeftButton,
                    pos=button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
                self.app.processEvents()

            click("statisticsSessionsTab")
            self.assertTrue(self.find_visual_item(window, "sessionHistoryEmpty").isVisible())
            self.assertFalse(self.find_visual_item(window, "gameStatisticsList").isVisible())
            self.assertTrue(self.find_visual_item(window, "sessionHistoryList").isVisible())
            picture = QImage(64, 32, QImage.Format_ARGB32)
            picture.fill(QColor("#258bd2"))
            path = Path(directory) / "cover.png"
            self.assertTrue(picture.save(str(path)))
            cover = QUrl.fromLocalFile(str(path)).toString()
            game = replace(GAME, title_icon_url=cover)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", game,
                cover_url=cover, game_started_at=int(clock.wall())-120))
            QTest.qWait(180)
            self.assertFalse(self.find_visual_item(window, "sessionHistoryEmpty").isVisible())
            self.assertEqual(controller.sessionHistory.rowCount(), 1)
            image = self.find_visual_item(window, "sessionHistoryCover0")
            self.assertTrue(image.property("imageReady"))
            point = image.mapToScene(QPointF(image.width()/2, image.height()/2)).toPoint()
            color = window.grabWindow().pixelColor(point)
            self.assertGreater(color.blue(), color.green()+30)
            resets = []
            controller.sessionHistory.modelReset.connect(lambda: resets.append(True))
            for _ in range(5):
                clock.value += 1
                controller._refresh_auth()
                self.app.processEvents()
            self.assertEqual(self.find_visual_item(window, "sessionHistoryDuration0").property("text"), "00:00:05")
            self.assertEqual(self.find_visual_item(window, "sessionHistoryEnd0").property("text"), "Последняя сессия: —")
            self.assertFalse(resets)
            self.assertIs(self.find_visual_item(window, "sessionHistoryCover0"), image)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.WAITING_FOR_PSN, "unavailable", "Player"))
            self.app.processEvents()
            self.assertIn("приостановлен", self.find_visual_item(window, "sessionHistoryState0").property("text"))
            clock.value += 20
            controller._refresh_auth()
            self.assertEqual(controller._statistics.history_rows()[0]["totalSeconds"], 5)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", game, cover_url=cover))
            self.assertEqual(controller.sessionHistory.rowCount(), 1)
            controller.set_snapshot(BridgeSnapshot(BridgePhase.ACTIVE, "playing", "Player", replace(OTHER, title_icon_url=cover), cover_url=cover))
            QTest.qWait(100)
            self.assertEqual(controller.sessionHistory.rowCount(), 2)
            self.assertEqual(controller._statistics.history_rows()[1]["state"], "Смена игры")
            controller.toggleNewYearThemeButton()
            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora", "newyear"):
                controller.saveTheme(theme)
                QTest.qWait(40)
                games_tab = self.find_visual_item(window, "statisticsGamesTab")
                sessions_tab = self.find_visual_item(window, "statisticsSessionsTab")
                self.assertAlmostEqual(games_tab.width(), sessions_tab.width(), delta=1, msg=theme)
                self.assertEqual(games_tab.height(), sessions_tab.height(), theme)
                game_card = self.find_visual_item(window, "statisticsGameRow0")
                session_card = self.find_visual_item(window, "sessionHistoryRow0")
                self.assertEqual(game_card.height(), 88, theme)
                self.assertEqual(session_card.height(), 132, theme)
                self.assertEqual(game_card.width(), session_card.width(), theme)
                for name in ("statisticsCover0", "sessionHistoryCover0"):
                    cover_image = self.find_visual_item(window, name)
                    self.assertEqual((cover_image.width(), cover_image.height()), (44, 44), (theme, name))
                    self.assertEqual((cover_image.x(), cover_image.y()), (2, 2), (theme, name))
                    self.assertAlmostEqual(cover_image.property("paintedWidth"), 44, delta=.1)
                    self.assertAlmostEqual(cover_image.property("paintedHeight"), 22, delta=.1)
                start = self.find_visual_item(window, "sessionHistoryStart0")
                end = self.find_visual_item(window, "sessionHistoryEnd0")
                # Native Windows fonts validate full glyph widths. Offscreen
                # metrics may measure unavailable fonts using fallback glyphs.
                if self.app.platformName() == "windows":
                    self.assertLessEqual(start.property("implicitWidth"), start.width(), theme)
                    previous_end = self.find_visual_item(window, "sessionHistoryEnd1")
                    self.assertLessEqual(previous_end.property("implicitWidth"), previous_end.width(), theme)
                self.assertTrue(start.property("text").startswith("Первая сессия: "), theme)
                self.assertTrue(end.property("text").startswith("Последняя сессия: "), theme)
                self.assertLessEqual(start.mapToScene(QPointF(0, start.height())).y(), end.mapToScene(QPointF(0, 0)).y(), theme)
            click("statisticsGamesTab")
            self.assertTrue(self.find_visual_item(window, "gameStatisticsList").isVisible())
            self.assertFalse(self.find_visual_item(window, "sessionHistoryList").isVisible())
            click("statisticsSessionsTab")
            click("closeStatisticsButton")
            self.assertFalse(window.property("statisticsVisible"))
            self.assertFalse(warnings)
            window.hide()

    def test_compact_game_cards_sort_by_numeric_playtime_and_last_launch(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            rows = [
                dict(gameKey=key, title=title, coverUrl="", playtime=duration, totalSeconds=seconds,
                     lastPlayedAt=date, sessionCount=1, isCurrent=False, isPaused=False, lastPlayed="1 октября 2026 · 10:00")
                for key, title, duration, seconds, date in (
                    ("long", "Long game", "100:00:00", 360000, 100),
                    ("old", "Older game", "99:59:59", 359999, 400),
                    ("short", "Short game", "00:00:10", 10, 300),
                    ("tie", "Another short game", "00:00:10", 10, 200))
            ]
            stack.enter_context(patch.object(controller._statistics, "rows", return_value=rows))
            controller._update_statistics_model()
            window.setProperty("statisticsVisible", True)
            QTest.qWait(200)
            time_button = self.find_visual_item(window, "statisticsTimeSortButton")
            recent_button = self.find_visual_item(window, "statisticsRecentSortButton")
            def order():
                return [row["gameKey"] for row in controller.gameStatistics._rows]
            def click(button):
                QTest.mouseClick(window, Qt.LeftButton,
                    pos=button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
                QTest.qWait(80)
            self.assertEqual(order(), ["long", "old", "tie", "short"])
            self.assertEqual(time_button.property("text"), "Время в игре ↓")
            self.assertEqual(self.find_visual_item(window, "statisticsGameRow0").height(), 88)
            click(time_button)
            self.assertEqual(order(), ["tie", "short", "old", "long"])
            self.assertEqual(time_button.property("text"), "Время в игре ↑")
            click(recent_button)
            self.assertEqual(order(), ["old", "short", "tie", "long"])
            self.assertEqual(recent_button.property("text"), "Последний запуск ↓")
            click(recent_button)
            self.assertEqual(order(), ["long", "tie", "short", "old"])
            controller.refreshStatistics()
            controller._language = "en"
            controller.language_changed.emit()
            QTest.qWait(60)
            self.assertEqual(order(), ["long", "tie", "short", "old"])
            self.assertEqual(recent_button.property("text"), "Last played ↑")
            self.assertEqual(time_button.property("text"), "Playtime")
            dialog = window.findChild(QObject, "gameStatisticsDialog")
            dialog.setProperty("historyMode", True)
            self.app.processEvents()
            self.assertFalse(time_button.isVisible())
            self.assertFalse(recent_button.isVisible())
            dialog.setProperty("historyMode", False)
            click(self.find_visual_item(window, "closeStatisticsButton"))
            window.setProperty("statisticsVisible", True)
            QTest.qWait(200)
            self.assertEqual(order(), ["long", "tie", "short", "old"])
            click(time_button)
            self.assertEqual(order(), ["long", "old", "tie", "short"])
            self.assertFalse(controller.statisticsSortAscending)
            controller.sortStatisticsBy("invalid")
            self.assertEqual(controller.statisticsSortMode, "playtime")
            self.assertFalse(controller.statisticsSortAscending)
            resets = []
            controller.gameStatistics.modelReset.connect(lambda: resets.append(True))
            controller.refreshStatistics()
            self.assertFalse(resets)
            self.assertEqual([row["gameKey"] for row in rows], ["long", "old", "short", "tie"])
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_statistics_soft_edges_follow_scroll_position_in_both_tabs(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("statisticsVisible", True)
            QTest.qWait(100)
            controller.gameStatistics.update([
                dict(gameKey=str(i), title="Test game", coverUrl="", playtime="01:02:03",
                     sessionCount=1, isCurrent=False, isPaused=False, lastPlayed="1 октября 2026")
                for i in range(4)
            ])
            controller.sessionHistory.update([
                dict(sessionKey=str(i), title="Test session", coverUrl="", playtime="00:12:34",
                     startedAt="1 октября 2026 · 10:00", endedAt="1 октября 2026 · 11:00",
                     state="Сессия завершена", isCurrent=False, isPaused=False)
                for i in range(4)
            ])
            dialog = window.findChild(QObject, "gameStatisticsDialog")
            top = self.find_visual_item(window, "statisticsTopFade")
            bottom = self.find_visual_item(window, "statisticsBottomFade")
            viewport = self.find_visual_item(window, "statisticsViewport")
            for theme in ("light", "oled", "aurora"):
                controller.saveTheme(theme)
                for history, name in ((False, "gameStatisticsList"), (True, "sessionHistoryList")):
                    dialog.setProperty("historyMode", history)
                    QTest.qWait(80)
                    view = self.find_visual_item(window, name)
                    origin = view.property("originY")
                    end = origin + view.property("contentHeight") - view.height()
                    self.assertGreater(end, origin)
                    view.setProperty("contentY", origin)
                    self.app.processEvents()
                    self.assertFalse(top.isVisible(), (theme, name))
                    self.assertTrue(bottom.isVisible(), (theme, name))
                    self.assertAlmostEqual(bottom.y() + bottom.height(), viewport.height(), delta=.1)
                    view.setProperty("contentY", (origin + end) / 2)
                    self.app.processEvents()
                    self.assertTrue(top.isVisible(), (theme, name))
                    self.assertTrue(bottom.isVisible(), (theme, name))
                    view.setProperty("contentY", end)
                    self.app.processEvents()
                    self.assertTrue(top.isVisible(), (theme, name))
                    self.assertFalse(bottom.isVisible(), (theme, name))
            controller.sessionHistory.update([])
            QTest.qWait(80)
            self.assertFalse(bottom.isVisible())
            self.assertFalse(top.isVisible())
            window.hide()

    def test_bulbs_receive_real_clicks_in_every_theme(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            controller.toggleNewYearThemeButton()
            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora", "newyear"):
                controller.saveTheme(theme)
                self.app.processEvents()
                for index in range(18):
                    lamp = self.find_visual_item(window, f"garlandLamp{index}")
                    self.assertIsNotNone(lamp)
                    if not lamp.property("bulbAvailable"):
                        continue
                    lamp.setProperty("lit", False)
                    point = self.art_point(window, lamp.x() + 130, lamp.y() + 260)
                    QTest.mouseClick(window, Qt.LeftButton, pos=point)
                    self.assertTrue(lamp.property("lit"), f"{theme}, lamp {index}")
                    QTest.mouseClick(window, Qt.LeftButton, pos=point)
                    self.assertFalse(lamp.property("lit"), f"{theme}, lamp {index}")
            # The bulb layer must not swallow clicks for the theme selector.
            QTest.qWait(200)
            swatch = self.find_visual_item(window, "themeHitTarget2")
            center = swatch.mapToScene(QPointF(swatch.width() / 2, swatch.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=center)
            self.app.processEvents()
            self.assertEqual(controller.themeId, "botanical")
            window.hide()

    def test_native_double_click_toggles_bulb_on_and_off_without_a_cooldown(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            lamp = self.find_visual_item(window, "garlandLamp0")
            point = self.art_point(window, lamp.x() + 130, lamp.y() + 260)
            QTest.mouseDClick(window, Qt.LeftButton, pos=point)
            QTest.mouseRelease(window, Qt.LeftButton, pos=point)
            self.assertFalse(lamp.property("lit"), "Both halves of a double click must toggle the bulb")
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertTrue(lamp.property("lit"), "The next click must relight while the fade is still running")
            window.hide()

    def test_botanical_low_left_bulb_click_glow_and_all_lights_switch(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            lamp = self.find_visual_item(window, "garlandLamp18")
            target = self.find_visual_item(window, "garlandHitTarget18")
            self.assertTrue(lamp.property("bulbAvailable"))
            self.assertEqual((lamp.x() + 130, lamp.y() + 260), (48, 252))
            self.assertEqual((lamp.property("glowOffsetX"), lamp.property("glowOffsetY")), (0, 13))
            point = self.previous_art_point(window, 43, 227)  # The same bulb in the new compact decoration layer.
            dark = window.grabWindow().pixelColor(self.previous_art_point(window, 43, 245))
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertTrue(lamp.property("lit"))
            self.assertGreaterEqual(lamp.property("glowLevel"), .28)
            QTest.qWait(250)
            bright = window.grabWindow().pixelColor(self.previous_art_point(window, 43, 245))
            self.assertGreater(bright.red() + bright.green(), dark.red() + dark.green() + 10)
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertFalse(lamp.property("lit"))
            for _ in range(3):
                QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 591, 385))
            self.assertTrue(lamp.property("lit"))
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 591, 385))
            self.assertFalse(lamp.property("lit"))
            controller.toggleNewYearThemeButton()
            for theme in ("light", "oled", "terracotta", "indigo", "sakura", "aurora", "newyear"):
                controller.saveTheme(theme)
                self.app.processEvents()
                self.assertFalse(lamp.property("bulbAvailable"), theme)
                self.assertFalse(target.isVisible(), theme)
                QTest.mouseMove(window, point)
                self.app.processEvents()
                self.assertEqual(window.cursor().shape(), Qt.ArrowCursor, theme)
            window.hide()

    def test_native_double_click_toggles_pinecone_on_and_off_without_a_cooldown(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            controller.toggleNewYearThemeButton()
            controller.saveTheme("newyear")
            self.app.processEvents()
            target = self.find_visual_item(window, "festivePineconeClick")
            point = target.mapToScene(QPointF(target.width() / 2, target.height() / 2)).toPoint()
            QTest.mouseDClick(window, Qt.LeftButton, pos=point)
            QTest.mouseRelease(window, Qt.LeftButton, pos=point)
            self.assertFalse(window.property("festiveAtmosphereActive"), "The double click must toggle twice")
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertTrue(window.property("festiveAtmosphereActive"))
            window.hide()

    def test_theme_specific_secret_targets_are_unmounted_and_have_no_ghost_cursor(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            controller.toggleNewYearThemeButton()
            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora", "newyear", "botanical"):
                controller.saveTheme(theme)
                self.app.processEvents()
                christmas = theme == "newyear"
                self.assertEqual(self.find_visual_item(window, "festivePineconeClick") is not None, christmas)
                self.assertEqual(self.find_visual_item(window, "secretLeafClick") is not None, not christmas)
                for point, expected in ((self.previous_art_point(window, 598, 294), christmas), (self.previous_art_point(window, 591, 385), not christmas)):
                    QTest.mouseMove(window, point)
                    self.app.processEvents()
                    self.assertEqual(window.cursor().shape(), Qt.PointingHandCursor if expected else Qt.ArrowCursor, (theme, point))
                for index in (8, 12):
                    target = self.find_visual_item(window, f"garlandHitTarget{index}")
                    self.assertEqual(target.isVisible(), not christmas)
            window.hide()

    def test_release_version_and_lamp_click_without_clipboard_changes(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            version = window.findChild(QObject, "programVersion")
            self.assertEqual(version.property("text"), "v. " + VERSION)
            self.assertFalse(version.isVisible())
            window.setProperty("aboutVisible", True)
            QTest.qWait(100)
            self.assertTrue(version.isVisible())
            point = version.mapToScene(QPointF(0, 0))
            self.assertGreaterEqual(point.x(), 0)
            self.assertLess(point.y() + version.height(), window.height())
            window.setProperty("aboutVisible", False)
            QTest.qWait(100)
            previous_clipboard = self.app.clipboard().text()
            self.app.clipboard().setText("keep clipboard")
            try:
                QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 72, 17))
                self.assertTrue(self.find_visual_item(window, "garlandLamp0").property("lit"))
                self.assertEqual(self.app.clipboard().text(), "keep clipboard")
                self.assertFalse(hasattr(controller, "copyLightCoordinates"))
                self.assertFalse(hasattr(controller, "saveLightOffset"))
                self.assertIsNone(self.find_visual_item(window, "lightTunerPanel"))
            finally:
                self.app.clipboard().setText(previous_clipboard)
            window.hide()

    def test_large_non_square_avatar_is_center_cropped_and_actually_drawn(self):
        with ExitStack() as stack, tempfile.TemporaryDirectory() as directory:
            controller, engine, window = self.create_window(stack)
            image = QImage(1024, 512, QImage.Format_ARGB32)
            image.fill(QColor("#20bc69"))
            painter = QPainter(image)
            painter.fillRect(0, 0, 256, 512, QColor("#ff0000"))
            painter.fillRect(768, 0, 256, 512, QColor("#0000ff"))
            painter.end()
            path = Path(directory) / "wide-avatar.png"
            self.assertTrue(image.save(str(path)))
            controller.set_snapshot(BridgeSnapshot(BridgePhase.IDLE, "idle", "Example", avatar_url=QUrl.fromLocalFile(str(path)).toString()))
            QTest.qWait(350)
            avatar = self.find_visual_item(window, "psnAvatar")
            picture = self.find_visual_item(window, "avatarPicture")
            self.assertTrue(avatar.property("imageReady"))
            self.assertEqual(picture.width(), avatar.width() * 2)
            screenshot = window.grabWindow()
            for x in (8, 17, 26):
                point = avatar.mapToScene(QPointF(x, 17)).toPoint()
                color = screenshot.pixelColor(point)
                self.assertGreater(color.green(), color.red() + 50, (x, color.name()))
                self.assertGreater(color.green(), color.blue() + 50, (x, color.name()))
            window.hide()

    def test_lowest_right_leaf_easter_egg_in_all_regular_themes(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora"):
                controller.saveTheme(theme)
                self.app.processEvents()
                # Actual centre of the lowest leaf in the scaled artwork.
                point = self.previous_art_point(window, 591, 385)
                for _ in range(3):
                    QTest.mouseClick(window, Qt.LeftButton, pos=point)
                    QTest.qWait(50)
                self.assertTrue(window.property("allLightsSecretActive"), theme)
                for index in range(18):
                    self.assertTrue(self.find_visual_item(window, f"garlandLamp{index}").property("lit"), theme)
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertFalse(window.property("allLightsSecretActive"), theme)
                for index in range(18):
                    self.assertFalse(self.find_visual_item(window, f"garlandLamp{index}").property("lit"), theme)
            window.hide()

    def test_leaf_mask_is_invokable_and_theme_switches_emit_no_qml_warnings(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(message) for message in messages))
            controller.toggleNewYearThemeButton()
            controller.saveTheme("newyear")
            self.app.processEvents()
            for theme in ("botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora"):
                controller.saveTheme(theme)
                self.app.processEvents()
                target = self.find_visual_item(window, "secretLeafClick")
                self.assertTrue(target.contains(target.mapFromScene(QPointF(self.previous_art_point(window, 591, 385)))), theme)
                self.assertFalse(target.contains(QPointF(-1, -1)), theme)
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_theme_hover_reaches_swatch_and_shows_tooltip(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            swatch = self.find_visual_item(window, "themeHitTarget0")
            center = swatch.mapToScene(QPointF(swatch.width()/2, swatch.height()/2)).toPoint()
            QTest.mouseMove(window, center)
            QTest.qWait(500)
            self.assertTrue(swatch.property("containsMouse"))
            self.assertTrue(swatch.property("tooltipShown"))
            self.assertEqual(window.property("themes").toVariant()[0]["name"], "Роса")
            window.hide()

    def test_leaf_can_relight_without_waiting_and_rejects_neighbouring_pixels(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            # The cannabis fan leaf is wider than the old heart-shaped leaf.
            # Test genuinely empty pixels in the current drawing, not its tips.
            for point in (self.previous_art_point(window, 566, 402), self.previous_art_point(window, 594, 367), self.previous_art_point(window, 598, 352)):
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertEqual(window.property("secretLeafClicks"), 0)
            point = self.previous_art_point(window, 591, 385)
            for _ in range(3):
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertTrue(window.property("allLightsSecretUnlocked"))
            self.assertTrue(window.property("allLightsSecretActive"))
            # No waiting for a timer or the fade animation, and no re-unlock sequence.
            for expected in (False, True, False, True, False, True):
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertEqual(window.property("allLightsSecretActive"), expected)
                for index in range(18):
                    self.assertEqual(self.find_visual_item(window, f"garlandLamp{index}").property("lit"), expected)
            window.hide()

    def test_global_light_switch_has_immediate_visible_attack_and_interruptible_fade(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            dark = window.grabWindow()
            point = self.previous_art_point(window, 591, 385)
            for _ in range(3):
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
            lamps = [self.find_visual_item(window, f"garlandLamp{index}") for index in range(18)]
            self.assertTrue(window.property("allLightsSecretActive"))
            for lamp in lamps:
                self.assertGreaterEqual(lamp.property("glowLevel"), .28,
                                        "The all-lights switch must show light immediately, not start from black")
            QTest.qWait(35)
            responsive = window.grabWindow()
            differences = []
            for x, y in ((180, 86), (90, 86), (252, 59), (315, 90)):
                old, new = dark.pixelColor(self.previous_art_point(window, x, y)), responsive.pixelColor(self.previous_art_point(window, x, y))
                differences.append(new.red() + new.green() + new.blue() - old.red() - old.green() - old.blue())
            self.assertGreater(max(differences), 8, "The switch must draw visible light, not only update flags")
            QTest.qWait(200)
            before = window.grabWindow()
            # Relight in the middle of the old fade; no cooldown or queued attack.
            for _ in range(4):
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertFalse(window.property("allLightsSecretActive"))
                QTest.qWait(35)
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                self.assertTrue(window.property("allLightsSecretActive"))
                for lamp in lamps:
                    self.assertTrue(lamp.property("lit"))
                    self.assertGreaterEqual(lamp.property("glowLevel"), .28)
                QTest.qWait(25)
            after = window.grabWindow()
            self.assertFalse(before.isNull())
            self.assertFalse(after.isNull())
            # A cancelled fade must never finish later and darken a relit bulb.
            QTest.qWait(250)
            for lamp in lamps:
                self.assertAlmostEqual(lamp.property("glowLevel"), 1, delta=.01)
            window.hide()

    def test_software_rendering_source_mode_loads_all_themes_and_dialogs(self):
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(project / "gui.py"),
                                 "--software-rendering", "--smoke-test"],
                                capture_output=True, text=True, timeout=15,
                                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_leaf_handles_double_clicks_and_really_draws_glow(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            QTest.qWait(200)
            before = window.grabWindow()
            point = self.previous_art_point(window, 591, 385)
            QTest.mouseDClick(window, Qt.LeftButton, pos=point)
            QTest.mouseRelease(window, Qt.LeftButton, pos=point)
            self.assertEqual(window.property("secretLeafClicks"), 2)
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            self.assertTrue(window.property("allLightsSecretActive"))
            QTest.qWait(750)
            after = window.grabWindow()
            differences = []
            for x, y in ((180, 86), (90, 86), (252, 59), (315, 90)):
                old = before.pixelColor(self.previous_art_point(window, x, y))
                new = after.pixelColor(self.previous_art_point(window, x, y))
                differences.append(new.red() + new.green() + new.blue() - old.red() - old.green() - old.blue())
            self.assertGreater(max(differences), 15, "Flags alone are not enough: the halo must be visible")
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(500)
            self.assertFalse(window.property("allLightsSecretActive"))
            window.hide()

    def test_pinecone_toggles_all_lights_and_snow(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            controller.toggleNewYearThemeButton()
            controller.saveTheme("newyear")
            self.app.processEvents()
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 598, 294))
            self.assertTrue(window.property("festiveAtmosphereActive"))
            for index in range(18):
                self.assertTrue(self.find_visual_item(window, f"garlandLamp{index}").property("lit"))
            snow = window.findChild(QObject, "festiveSnowfall")
            self.assertTrue(snow.property("active"))
            QTest.qWait(150)
            self.assertGreater(snow.property("elapsed"), 0)
            window.hide()
            elapsed = snow.property("elapsed")
            QTest.qWait(100)
            self.assertEqual(snow.property("elapsed"), elapsed)
            window.show()
            # Snow is click-through: a second real click still reaches the cone.
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 598, 294))
            self.assertFalse(window.property("festiveAtmosphereActive"))
            self.assertFalse(snow.property("active"))
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 598, 294))
            controller.saveTheme("botanical")
            self.app.processEvents()
            self.assertFalse(window.property("festiveAtmosphereActive"))
            # The original leaf Easter egg must still work after switching themes.
            for _ in range(3):
                QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 585, 380))
            self.assertTrue(window.property("allLightsSecretActive"))
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 585, 380))
            self.assertFalse(window.property("allLightsSecretActive"))
            window.hide()

    def test_botanical_leaf_fall_toggles_pauses_and_does_not_block_clicks(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            warnings = []
            engine.warnings.connect(lambda messages: warnings.extend(str(m) for m in messages))
            leaves = self.find_visual_item(window, "botanicalLeafFall")
            self.assertFalse(leaves.property("active"))
            self.assertEqual(leaves.property("particleCount"), 0)
            for _ in range(3):
                QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 591, 385))
            self.assertTrue(leaves.property("active"))
            QTest.qWait(200)
            self.assertEqual(leaves.property("particleCount"), 28)
            leaf = self.find_visual_item(window, "fallingCannabisLeaf0")
            self.assertTrue(leaf.property("imageReady"))
            self.assertEqual(leaf.property("sourceClipRect").width(), 126)
            self.assertEqual((leaf.implicitWidth(), leaf.implicitHeight()), (126, 85))
            y, rotation = leaf.y(), leaf.rotation()
            QTest.qWait(100)
            self.assertGreater(leaf.y(), y)
            self.assertNotEqual(leaf.rotation(), rotation)
            self.assertGreater(leaves.property("elapsed"), 0)
            window.hide()
            elapsed = leaves.property("elapsed")
            QTest.qWait(100)
            self.assertEqual(leaves.property("elapsed"), elapsed)
            window.show()
            window.setProperty("settingsVisible", True)
            self.app.processEvents()
            self.assertFalse(leaves.property("animating"))
            window.setProperty("settingsVisible", False)
            self.app.processEvents()
            self.assertTrue(leaves.property("animating"))
            # Put a real particle over the bulb: its image is still click-through.
            leaf.setX(40); leaf.setY(240)
            lamp = self.find_visual_item(window, "garlandLamp18")
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 43, 227))
            self.assertFalse(lamp.property("lit"))
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 591, 385))
            self.assertFalse(leaves.property("active"))
            QTest.qWait(1200)
            self.assertFalse(leaves.isVisible(), f"intensity={leaves.property('intensity')}, active={leaves.property('active')}")
            self.assertEqual(leaves.property("particleCount"), 0)
            QTest.mouseClick(window, Qt.LeftButton, pos=self.previous_art_point(window, 591, 385))
            self.assertTrue(leaves.property("active"))
            controller.saveTheme("aurora")
            self.app.processEvents()
            self.assertFalse(leaves.property("active"))
            self.assertFalse(leaves.isVisible())
            self.assertFalse(leaves.property("animating"))
            self.assertFalse(warnings, warnings)
            window.hide()

    def test_scaled_dialogs_are_visually_centered(self):
        with ExitStack() as stack:
            controller, engine, window = self.create_window(stack)
            for visible, name in (("settingsVisible", "settingsDialog"), ("npssoVisible", "npssoDialog"), ("statisticsVisible", "gameStatisticsDialog")):
                window.setProperty(visible, True)
                QTest.qWait(200)
                dialog = window.findChild(QObject, name)
                scale = dialog.property("scale")
                self.assertAlmostEqual(dialog.property("x") + dialog.property("width") * scale / 2, window.width() / 2, delta=1)
                self.assertAlmostEqual(dialog.property("y") + dialog.property("height") * scale / 2, window.height() / 2, delta=1)
                window.setProperty(visible, False)
                QTest.qWait(200)
            window.hide()

    def test_secret_code_toggles_button_and_reverts_selected_theme(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(patch("qml_app.is_new_year_theme_available", return_value=False))
            stack.enter_context(patch("qml_app.load_npsso", return_value="test"))
            stack.enter_context(patch("qml_app.load_npsso_expires_at", return_value=None))
            stack.enter_context(patch("qml_app.load_configuration", return_value=StoredConfiguration()))
            save = stack.enter_context(patch("qml_app.save_theme", side_effect=lambda theme: theme))
            controller = PresenceController(statistics_path=None)
            controller._clock.stop()
            engine = QQmlApplicationEngine()
            engine.rootContext().setContextProperty("presence", controller)
            engine.load(QUrl.fromLocalFile(str(QML_FILE)))
            self.assertEqual(len(engine.rootObjects()), 1)
            window = engine.rootObjects()[0]
            key_filter = SecretThemeKeyFilter(window, controller)
            window.show()
            window.requestActivate()
            QTest.qWait(50)

            def enter_code(modifier=Qt.NoModifier, pause=0) -> None:
                for key in (Qt.Key_3, Qt.Key_1, Qt.Key_1, Qt.Key_2):
                    QTest.keyClick(window, key, modifier)
                    if pause:
                        QTest.qWait(pause)
                self.app.processEvents()

            # Typing digits into settings must not trigger the Easter egg.
            window.setProperty("settingsVisible", True)
            self.app.processEvents()
            enter_code()
            self.assertFalse(controller.newYearThemeAvailable)
            window.setProperty("settingsVisible", False)
            self.app.processEvents()

            QTest.mouseClick(window, Qt.LeftButton, pos=QPoint(100, 450))
            # Read-only log focus and slow typing must not block the sequence.
            enter_code(pause=1100)
            self.assertTrue(controller.newYearThemeAvailable)
            controller.saveTheme("newyear")
            self.app.processEvents()
            self.assertEqual(window.property("currentThemeIndex"), 7)
            save.assert_not_called()  # Out-of-season unlock is session-only.

            enter_code(Qt.KeypadModifier)
            self.assertFalse(controller.newYearThemeAvailable)
            self.assertEqual(controller.themeId, "aurora")
            self.assertEqual(window.property("currentThemeIndex"), 6)
            enter_code(Qt.ControlModifier)
            self.assertFalse(controller.newYearThemeAvailable)
            window.hide()


if __name__ == "__main__":
    unittest.main()
