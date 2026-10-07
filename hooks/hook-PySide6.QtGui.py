"""Keep raster/SVG image support, but do not ship a PDF rendering engine."""
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [entry for entry in binaries if Path(entry[0]).name.casefold() != 'qpdf.dll']
