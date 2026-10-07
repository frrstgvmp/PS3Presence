"""Collect the QML modules used by this app, not the entire Qt SDK.

Filter before PyInstaller scans plugin DLL dependencies: removing WebEngine
after analysis would leave its other binaries and resources in the release.
Keep the selected Basic style and its supporting modules for indirect imports.
"""
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info
from packaging_policy import qml_module_is_used

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()
qml_root = Path(pyside6_library_info.location['QmlImportsPath']).resolve()


def used_by_application(entry):
    source = Path(entry[0]).resolve()
    return qml_module_is_used(source.relative_to(qml_root), is_directory=source.is_dir())


binaries += [entry for entry in qml_binaries if used_by_application(entry)]
datas += [entry for entry in qml_datas if used_by_application(entry)]
