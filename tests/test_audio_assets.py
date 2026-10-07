import tempfile
import unittest
import wave
from pathlib import Path

from audio_assets import read_pcm_note


class AudioAssetTests(unittest.TestCase):
    def write_wav(self, path, channels=1, width=2, data=b"\x00" * 88200):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(width)
            output.setframerate(44100)
            output.writeframes(data)

    def test_reads_exact_pcm_frames_and_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.wav"
            self.write_wav(path)
            note = read_pcm_note(path)
            self.assertEqual(note.data, b"\x00" * 88200)
            self.assertEqual(note.channels, 1)
            self.assertEqual(note.sample_rate, 44100)
            self.assertEqual(note.duration, 1)

    def test_rejects_empty_and_non_16_bit_pcm(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.wav"
            for width, data in ((2, b""), (1, b"\x00" * 100)):
                self.write_wav(path, width=width, data=data)
                with self.assertRaises(ValueError):
                    read_pcm_note(path)

    def test_rejects_truncated_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.wav"
            self.write_wav(path)
            path.write_bytes(path.read_bytes()[:-100])
            with self.assertRaises(ValueError):
                read_pcm_note(path)

    def test_all_generated_notes_are_non_silent_and_originals_are_preserved(self):
        project = Path(__file__).resolve().parents[1]
        for index in range(1, 37):
            self.assertTrue((project / "design" / "newyear" / "audio" / f"sound{index}.mp3").is_file())
            note = read_pcm_note(project / "assets" / "newyear" / "pcm" / f"sound{index}.wav")
            self.assertGreater(note.duration, .5)
            self.assertTrue(any(note.data), index)
