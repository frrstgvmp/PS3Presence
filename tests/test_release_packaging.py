from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app_metadata import RELEASE_VERSION
from packaging_policy import QML_FILES, RUNTIME_ASSETS, RUNTIME_SCRIPTS
from tools import package_release


class ReleasePackagingTests(unittest.TestCase):
    def make_release(self, root: Path) -> Path:
        directory = root / "releases" / RELEASE_VERSION
        app = directory / "PS3Presence"
        files = [app / "PS3Presence.exe", directory / "README.txt", directory / "LICENSE"]
        files += [app / "_internal" / "assets" / name for name in RUNTIME_ASSETS]
        files += [app / "_internal" / "qml" / name for name in QML_FILES]
        files += [app / "_internal" / name for name in RUNTIME_SCRIPTS]
        files += [app / "_internal" / "licenses" / name for name in
                  ("THIRD_PARTY_NOTICES.txt", "Qt/LGPL-3.0-only.txt", "Qt/GPL-3.0-only.txt", "OpenSSL/LICENSE.txt", "Python/LICENSE.txt")]
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test release content")
        return directory

    def test_zip_contains_complete_runtime_instructions_licenses_and_valid_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = self.make_release(root)
            with patch.object(package_release, "PROJECT_DIR", root), patch("sys.argv", ["package_release.py", str(directory)]), redirect_stdout(io.StringIO()):
                self.assertEqual(package_release.main(), 0)
                archive = directory / f"PS3Presence-{RELEASE_VERSION}-win64-portable.zip"
                with zipfile.ZipFile(archive) as output:
                    self.assertIsNone(output.testzip())
                    for name in ("README.txt", "LICENSE", "PS3Presence/PS3Presence.exe",
                                 "PS3Presence/_internal/licenses/Qt/LGPL-3.0-only.txt"):
                        self.assertIn(name, output.namelist())
                expected = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertEqual((directory / "SHA256SUMS.txt").read_text().strip(), f"{expected}  {archive.name}")
                with self.assertRaises(FileExistsError):
                    package_release.main()

    def test_missing_project_license_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = self.make_release(Path(folder))
            (directory / "LICENSE").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "Release LICENSE"):
                package_release.validate_release(directory)

    def test_missing_third_party_license_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = self.make_release(Path(folder))
            (directory / "PS3Presence/_internal/licenses/Qt/LGPL-3.0-only.txt").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "Third-party notice"):
                package_release.validate_release(directory)

    def test_private_runtime_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = self.make_release(Path(folder))
            (directory / "PS3Presence/.env").write_text("test only")
            with self.assertRaisesRegex(ValueError, "Private runtime data"):
                package_release.validate_release(directory)
