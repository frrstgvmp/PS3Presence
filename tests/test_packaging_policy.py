from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from packaging_policy import RUNTIME_ASSETS, QML_FILES, qml_module_is_used, runtime_data, runtime_data_is_used

PROJECT_DIR = Path(__file__).resolve().parents[1]


class PackagingPolicyTests(unittest.TestCase):
    def test_runtime_manifest_contains_only_active_art_icon_and_36_pcm_notes(self):
        entries = runtime_data(PROJECT_DIR)
        self.assertEqual(len(entries), 54)
        self.assertTrue(any(source.endswith("ConnectionIndicator.qml") for source, _ in entries))
        self.assertTrue(any(source.endswith("FallingPhrase.qml") for source, _ in entries))
        self.assertTrue(any(source.endswith("install_autostart.ps1") for source, _ in entries))
        self.assertEqual(len([name for name in RUNTIME_ASSETS if name.endswith(".wav")]), 36)
        self.assertFalse(any("draft" in source or source.endswith(".mp3") for source, _ in entries))
        self.assertFalse(any("design" in source for source, _ in entries))

    def test_missing_required_assets_fail_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                runtime_data(Path(directory))

    def test_basic_style_and_supporting_qml_imports_are_included(self):
        for path in ("QML/qmldir", "QtQml/Models/qmldir", "QtQml/WorkerScript/qmldir",
                     "QtQuick/qmldir", "QtQuick/Controls/qmldir", "QtQuick/Controls/Basic/Button.qml",
                     "QtQuick/Controls/Basic/impl/qmldir", "QtQuick/Controls/impl/qmldir",
                     "QtQuick/Layouts/qmldir", "QtQuick/Templates/qmldir", "QtQuick/Window/qmldir"):
            self.assertTrue(qml_module_is_used(path), path)

    def test_other_styles_browsers_3d_and_pdf_are_not_collected(self):
        for path in ("QtWebEngine/qmldir", "QtWebView/qmldir", "QtQuick3D/qmldir",
                     "QtQuick/Pdf/qmldir", "QtQuick/Shapes/qmldir", "QtQuick/Controls/Fusion/qmldir",
                     "QtQuick/Controls/FluentWinUI3/qmldir", "QtQuick/Controls/Windows/qmldir",
                     "QtQuick/plugins.qmltypes", "QtQuick/designer/metadata.qml",
                     "../QtQuick/qmldir", "/QtQuick/qmldir"):
            self.assertFalse(qml_module_is_used(path), path)
        self.assertFalse(qml_module_is_used("QtQuick/Controls", is_directory=True))
        self.assertTrue(qml_module_is_used("QtQuick/Controls/Basic", is_directory=True))
        self.assertFalse(qml_module_is_used("QtQuick/Controls/Fusion", is_directory=True))

    def test_country_databases_and_russian_qt_translation_are_preserved(self):
        self.assertTrue(runtime_data_is_used("pycountry/databases/iso3166-1.json"))
        self.assertFalse(runtime_data_is_used("pycountry/locales/de/LC_MESSAGES/iso3166-1.mo"))
        self.assertTrue(runtime_data_is_used("PySide6/translations/qtbase_ru.qm"))
        self.assertFalse(runtime_data_is_used("PySide6/translations/qtbase_de.qm"))
        self.assertTrue(runtime_data_is_used("assets/newyear/pcm/sound1.wav"))

    def test_runtime_does_not_import_gui_from_controller_or_use_a_media_decoder(self):
        for name in ("qml_app.py", "garland_audio.py"):
            tree = ast.parse((PROJECT_DIR / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "gui")
                    self.assertFalse(any(alias.name == "QAudioDecoder" for alias in node.names))

    def test_every_local_qml_art_reference_is_in_the_manifest(self):
        for name in QML_FILES:
            content = (PROJECT_DIR / "qml" / name).read_text(encoding="utf-8")
            import re
            for referenced in re.findall(r'\.\./assets/([^"\s]+)', content):
                self.assertIn(referenced, RUNTIME_ASSETS)
