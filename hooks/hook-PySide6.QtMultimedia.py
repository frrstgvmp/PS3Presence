"""Raw PCM playback uses QAudioSink in the core library, not media plugins.

No QMediaPlayer, decoder, camera, video widgets or true_properties are used
at runtime. The build-time audio preparation tool still uses installed codecs.
"""
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [entry for entry in binaries if Path(entry[0]).parent.name != 'multimedia']
