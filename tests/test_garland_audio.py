from __future__ import annotations

import os
import time
import unittest
import wave
from contextlib import ExitStack
from unittest.mock import patch

from runtime_bootstrap import prepare_native_libraries

prepare_native_libraries()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QObject, QPoint, Qt
from PySide6.QtMultimedia import QAudioFormat, QtAudio
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from garland_audio import GarlandAudio, Note, fade_volume
from tests import test_qml_theme_shortcut as qml_tests


def pcm_format():
    result = QAudioFormat()
    result.setSampleRate(44100)
    result.setChannelCount(1)
    result.setSampleFormat(QAudioFormat.Int16)
    return result


class FakeDevice:
    def isNull(self):
        return False

    def preferredFormat(self):
        return pcm_format()


class FakeSink(QObject):
    def __init__(self, device, format, parent):
        super().__init__(parent)
        self.level = 1.0
        self.stopped = False
        self.started_at = None

    def setBufferSize(self, _size):
        pass

    def setVolume(self, level):
        self.level = level

    def start(self, buffer):
        self.started_at = buffer.pos()

    def stop(self):
        self.stopped = True

    def error(self):
        return QtAudio.NoError

    def state(self):
        return QtAudio.ActiveState


class GarlandAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def fake_audio(self, stack):
        stack.enter_context(patch("garland_audio.QAudioSink", FakeSink))
        stack.enter_context(patch("garland_audio.QMediaDevices.defaultAudioOutput", return_value=FakeDevice()))
        audio = GarlandAudio()
        stack.callback(audio.shutdown)
        audio._active = True
        audio._notes = {i: Note(QByteArray(b"\x00" * 264600), pcm_format(), 3.0) for i in range(36)}
        return audio

    def test_restart_polyphony_and_one_second_release(self):
        with ExitStack() as stack:
            audio = self.fake_audio(stack)
            events = []
            audio.noteTriggered.connect(lambda lamp, note: events.append((lamp, note)))
            audio.enter(0)
            first = audio._voices[0]
            audio.leave(0)
            first.fade_started = time.monotonic() - .5
            audio._advance()
            self.assertAlmostEqual(first.sink.level, 10 ** -.5, delta=.02)
            self.assertFalse(first.sink.stopped)
            audio.enter(1)
            audio.enter(0)
            audio.enter(37)
            self.assertEqual(events, [(0, 0), (1, 1), (0, 0), (37, 1)])
            self.assertEqual(len(audio._voices), 4)
            self.assertTrue(all(v.sink.started_at == 0 for v in audio._voices))
            first.fade_started = time.monotonic() - 1.01
            audio._advance()
            self.assertTrue(first.sink.stopped)
            self.assertNotIn(first, audio._voices)
            audio.setActive(False)
            self.assertFalse(audio._voices)
            self.assertFalse(audio._tick.isActive())
            self.assertFalse(audio._hovered)

    def test_bound_cleanup_and_envelope(self):
        with ExitStack() as stack:
            audio = self.fake_audio(stack)
            for _ in range(100):
                audio.enter(0)
            self.assertEqual(len(audio._voices), 64)
            audio.shutdown()
            self.assertFalse(audio._notes)
            self.assertFalse(audio._voices)
            audio.setActive(True)
            self.assertFalse(audio.active)
        self.assertEqual(fade_volume(0), 1)
        self.assertEqual(fade_volume(1), 0)
        self.assertLess(fade_volume(.999), .003)

    def test_prepared_36_notes_preload_and_cache_survive_theme_switch(self):
        with ExitStack() as stack:
            stack.enter_context(patch("garland_audio.QMediaDevices.defaultAudioOutput", return_value=FakeDevice()))
            audio = GarlandAudio()
            stack.callback(audio.shutdown)
            warnings = []
            audio.warning.connect(warnings.append)
            audio.setActive(True)
            deadline = time.monotonic() + 10
            while audio.readyCount != 36 and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertEqual(audio.readyCount, 36, warnings)
            self.assertFalse(warnings)
            self.assertTrue(all(n.data.size() > 0 and n.duration > .5 for n in audio._notes.values()))
            self.assertFalse(hasattr(audio, "_decoder"))
            notes = dict(audio._notes)
            audio.setActive(False)
            audio.setActive(True)
            QTest.qWait(30)
            self.assertTrue(all(audio._notes[i] is notes[i] for i in range(36)))

    def test_invalid_pcm_warns_without_crashing_or_playing(self):
        audio = GarlandAudio()
        warnings = []
        audio.warning.connect(warnings.append)
        audio._active = True
        try:
            with patch("garland_audio.read_pcm_note", side_effect=wave.Error("invalid PCM")):
                audio._load_next()
            self.assertEqual(audio._failed, {0})
            self.assertFalse(audio._notes)
            self.assertFalse(audio._voices)
            self.assertEqual(len(warnings), 1)
        finally:
            audio.shutdown()

    def test_note_left_before_preload_finishes_never_plays_late(self):
        with ExitStack() as stack:
            audio = self.fake_audio(stack)
            events = []
            audio.noteTriggered.connect(lambda lamp, note: events.append((lamp, note)))
            del audio._notes[2]
            audio.enter(2)
            audio.leave(2)
            audio._load_next()
            self.assertFalse(events)
            self.assertFalse(audio._voices)
            audio.setActive(False)
            self.assertFalse(audio._next.isActive())

    def test_hovered_note_plays_once_when_pcm_preload_finishes(self):
        with ExitStack() as stack:
            audio = self.fake_audio(stack)
            events = []
            audio.noteTriggered.connect(lambda lamp, note: events.append((lamp, note)))
            del audio._notes[2]
            audio.enter(2)
            self.assertFalse(events)
            audio._load_next()
            self.assertEqual(events, [(2, 2)])
            audio._load_next()
            self.assertEqual(events, [(2, 2)])

    def test_fast_real_pointer_moves_and_other_themes_remain_silent(self):
        helper = qml_tests.SeasonalThemeShortcutTests()
        helper.app = self.app
        with ExitStack() as stack:
            stack.enter_context(patch("garland_audio.QAudioSink", FakeSink))
            stack.enter_context(patch("garland_audio.QMediaDevices.defaultAudioOutput", return_value=FakeDevice()))
            controller, engine, window = helper.create_window(stack)
            window.setProperty("decorationsEnabled", True)
            audio = controller.garlandAudio
            stack.callback(audio.shutdown)
            audio._notes = {i: Note(QByteArray(b"\x00" * 264600), pcm_format(), 3.0) for i in range(36)}
            events = []
            audio.noteTriggered.connect(lambda lamp, note: events.append((lamp, note)))
            controller.toggleNewYearThemeButton()
            controller.saveTheme("newyear")
            self.app.processEvents()
            QTest.mouseMove(window, QPoint(300, 400))
            for index in (0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 13, 14, 15, 16, 17):
                lamp = helper.find_visual_item(window, f"garlandLamp{index}")
                point = helper.art_point(window, lamp.x() + 130, lamp.y() + 260)
                QTest.mouseMove(window, point, delay=5)
                self.app.processEvents()
                self.assertTrue(events and events[-1] == (index, index), (index, events))
            self.assertEqual(len(events), 16, events)
            QTest.mouseMove(window, QPoint(300, 400))
            self.assertTrue(all(v.fade_started is not None for v in audio._voices))
            window.setProperty("settingsVisible", True)
            self.app.processEvents()
            self.assertFalse(audio.active)
            self.assertFalse(audio._voices)
            window.setProperty("settingsVisible", False)
            controller.saveTheme("botanical")
            self.app.processEvents()
            before = len(events)
            QTest.mouseMove(window, helper.art_point(window, 80, 19))
            self.assertEqual(len(events), before)
            self.assertFalse(audio.active)
            controller.saveTheme("newyear")
            self.app.processEvents()
            window.hide()
            self.app.processEvents()
            self.assertFalse(audio.active)
            self.assertFalse(audio._voices)


if __name__ == "__main__":
    unittest.main()
