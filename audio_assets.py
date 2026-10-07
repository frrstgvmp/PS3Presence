"""Validated PCM assets; no media decoder or GUI is needed to read a note."""
from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PCMNote:
    data: bytes
    sample_rate: int
    channels: int

    @property
    def duration(self) -> float:
        return len(self.data) / (self.sample_rate * self.channels * 2)


def read_pcm_note(path: Path) -> PCMNote:
    with wave.open(str(path), "rb") as recording:
        channels, width, rate, frames, compression, _ = recording.getparams()
        if width != 2 or channels not in (1, 2) or rate <= 0 or compression != "NONE":
            raise ValueError(f"Unsupported PCM format in {path.name}")
        data = recording.readframes(frames)
        if frames <= 0 or len(data) != frames * channels * width:
            raise ValueError(f"Empty or truncated PCM recording: {path.name}")
        return PCMNote(data, rate, channels)
