"""Cached PCM notes with independent voices and soft release tails.

MP3 decoding is a build-time job. Playback uses only QAudioSink, so the
release does not need media plugins or FFmpeg/video codec libraries.
"""
from __future__ import annotations

import time
import wave
from dataclasses import dataclass
from pathlib import Path

from runtime_bootstrap import prepare_native_libraries

prepare_native_libraries()

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Property, QTimer, Signal, Slot
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QtAudio

from audio_assets import read_pcm_note


@dataclass
class Note:
    data: QByteArray
    format: QAudioFormat
    duration: float


@dataclass
class Voice:
    lamp: int
    sink: QAudioSink
    buffer: QBuffer
    deadline: float
    fade_started: float | None = None


def fade_volume(elapsed: float) -> float:
    """NNM's 1 -> .1 exponential envelope, with a final 50 ms soft release."""
    if elapsed >= 1:
        return 0.0
    level = 10 ** -max(0.0, elapsed)
    return level * min(1.0, max(0.0, (1 - elapsed) / .05))


class GarlandAudio(QObject):
    changed = Signal()
    warning = Signal(str)
    noteTriggered = Signal(int, int)

    def __init__(self, parent=None, directory: Path | None = None):
        super().__init__(parent)
        self.directory = directory or Path(__file__).resolve().parent / "assets" / "newyear" / "pcm"
        self._active = False
        self._closed = False
        self._notes: dict[int, Note] = {}
        self._failed: set[int] = set()
        self._voices: list[Voice] = []
        self._hovered: set[int] = set()
        self._next = QTimer(self)
        self._next.setSingleShot(True)
        self._next.timeout.connect(self._load_next)
        self._tick = QTimer(self)
        self._tick.setInterval(10)
        self._tick.timeout.connect(self._advance)
        self._warned_output = False

    readyCount = Property(int, lambda self: len(self._notes), notify=changed)
    active = Property(bool, lambda self: self._active, notify=changed)

    @Slot(bool)
    def setActive(self, active: bool):
        if self._closed or active == self._active:
            return
        self._active = active
        self.changed.emit()
        if active:
            self._next.start(0)
        else:
            self._next.stop()
            self._hovered.clear()
            self.stopAll()

    def _load_next(self):
        if not self._active or self._closed:
            return
        index = next((i for i in range(36) if i not in self._notes and i not in self._failed), None)
        if index is None:
            return
        path = self.directory / f"sound{index + 1}.wav"
        try:
            pcm = read_pcm_note(path)
        except (OSError, ValueError, EOFError, wave.Error) as error:
            self._failed.add(index)
            self.warning.emit(f"Гирлянда: {path.name} — {error}")
            self._next.start(0)
            return
        format = QAudioFormat()
        format.setSampleRate(pcm.sample_rate)
        format.setChannelCount(pcm.channels)
        format.setSampleFormat(QAudioFormat.Int16)
        self._notes[index] = Note(QByteArray(pcm.data), format, pcm.duration)
        self.changed.emit()
        # If the pointer is still on a note during the initial preload, play it
        # once ready. A note already left must never fire belatedly.
        for lamp in tuple(self._hovered):
            if lamp % 36 == index:
                self._play(lamp)
        self._next.start(0)

    @Slot(int)
    def enter(self, lamp: int):
        if not self._active or lamp < 0:
            return
        self.leave(lamp)
        self._hovered.add(lamp)
        self._play(lamp)

    def _play(self, lamp: int):
        note = self._notes.get(lamp % 36)
        if note is None:
            return
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            if not self._warned_output:
                self.warning.emit("Гирлянда: устройство вывода звука недоступно")
                self._warned_output = True
            return
        # No global debounce: independent voices allow neighboring notes and
        # release tails to overlap. A hard bound also handles extreme re-entry.
        if len(self._voices) >= 64:
            self._dispose(self._voices[0])
        buffer = QBuffer(self)
        buffer.setData(note.data)
        buffer.open(QIODevice.ReadOnly)
        sink = QAudioSink(device, note.format, self)
        sink.setBufferSize(max(1, note.format.bytesForDuration(20_000)))
        sink.setVolume(1.0)
        voice = Voice(lamp, sink, buffer, time.monotonic() + note.duration + .1)
        self._voices.append(voice)
        sink.start(buffer)
        if sink.error() != QtAudio.NoError:
            self.warning.emit(f"Гирлянда: не удалось воспроизвести sound{lamp % 36 + 1}.wav")
            self._dispose(voice)
            return
        self.noteTriggered.emit(lamp, lamp % 36)
        self._tick.start()

    @Slot(int)
    def leave(self, lamp: int):
        self._hovered.discard(lamp)
        now = time.monotonic()
        for voice in self._voices:
            if voice.lamp == lamp and voice.fade_started is None:
                voice.fade_started = now

    def _advance(self):
        now = time.monotonic()
        for voice in tuple(self._voices):
            elapsed = None if voice.fade_started is None else now - voice.fade_started
            if now >= voice.deadline or (elapsed is not None and elapsed >= 1) or voice.sink.state() == QtAudio.IdleState:
                self._dispose(voice)
            elif elapsed is not None:
                voice.sink.setVolume(fade_volume(elapsed))
        if not self._voices:
            self._tick.stop()

    def _dispose(self, voice: Voice):
        voice.sink.stop()
        voice.buffer.close()
        voice.sink.deleteLater()
        voice.buffer.deleteLater()
        self._voices.remove(voice)

    @Slot()
    def stopAll(self):
        self._tick.stop()
        for voice in tuple(self._voices):
            self._dispose(voice)

    @Slot()
    def shutdown(self):
        self.setActive(False)
        self._closed = True
        self._notes.clear()
        self._hovered.clear()
