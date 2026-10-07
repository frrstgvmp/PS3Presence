"""Decode original MP3 notes once at build time into standard 16-bit PCM WAV."""
from __future__ import annotations

import sys
import wave
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from runtime_bootstrap import prepare_native_libraries

prepare_native_libraries()

from PySide6.QtCore import QCoreApplication, QObject, QTimer, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

from audio_assets import read_pcm_note


class AudioPreparer(QObject):
    def __init__(self, app: QCoreApplication):
        super().__init__(app)
        self.app = app
        self.source = PROJECT_DIR / "design" / "newyear" / "audio"
        self.destination = PROJECT_DIR / "assets" / "newyear" / "pcm"
        self.index = 0
        self.decoder = None
        self.chunks = bytearray()
        self.format = QAudioFormat()
        self.format.setSampleRate(44100)
        self.format.setChannelCount(1)
        self.format.setSampleFormat(QAudioFormat.Int16)

    def start(self):
        for index in range(1, 37):
            path = self.source / f"sound{index}.mp3"
            if not path.is_file():
                raise FileNotFoundError(path)
        self.destination.mkdir(parents=True, exist_ok=True)
        QTimer.singleShot(0, self.load_next)

    def release_decoder(self):
        decoder, self.decoder = self.decoder, None
        if decoder is not None:
            decoder.bufferReady.disconnect(self.read_buffer)
            decoder.finished.disconnect(self.finished)
            decoder.error.disconnect(self.error)
            decoder.stop()
            decoder.deleteLater()

    def load_next(self):
        if self.index == 36:
            print("Prepared and validated 36 PCM notes; original MP3 files unchanged.")
            self.app.exit(0)
            return
        self.chunks.clear()
        self.decoder = QAudioDecoder(self)
        self.decoder.bufferReady.connect(self.read_buffer)
        self.decoder.finished.connect(self.finished)
        self.decoder.error.connect(self.error)
        self.decoder.setAudioFormat(self.format)
        self.decoder.setSource(QUrl.fromLocalFile(str(self.source / f"sound{self.index + 1}.mp3")))
        self.decoder.start()

    def read_buffer(self):
        if self.decoder is None:
            return
        buffer = self.decoder.read()
        if buffer.isValid():
            if buffer.format() != self.format:
                self.fail("Decoder returned an unexpected PCM format")
                return
            self.chunks.extend(bytes(buffer.constData())[:buffer.byteCount()])

    def finished(self):
        if not self.chunks or len(self.chunks) % 2:
            self.fail("Empty or incomplete decoded PCM")
            return
        path = self.destination / f"sound{self.index + 1}.wav"
        temporary = path.with_suffix(".wav.tmp")
        try:
            with wave.open(str(temporary), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(44100)
                output.writeframes(self.chunks)
            read_pcm_note(temporary)
            temporary.replace(path)
        except (OSError, ValueError, wave.Error) as error:
            self.fail(str(error))
            return
        self.release_decoder()
        self.index += 1
        QTimer.singleShot(0, self.load_next)

    def error(self, code):
        if code != QAudioDecoder.NoError and self.decoder is not None:
            self.fail(self.decoder.errorString())

    def fail(self, message):
        print(f"sound{self.index + 1}.mp3: {message}", file=sys.stderr)
        self.release_decoder()
        self.app.exit(1)


def main() -> int:
    app = QCoreApplication(sys.argv[:1])
    preparer = AudioPreparer(app)
    preparer.start()
    QTimer.singleShot(60_000, app, lambda: app.exit(2))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
