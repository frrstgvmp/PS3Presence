"""Validate a clean portable folder, write its ZIP, verify CRCs and save SHA256."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app_metadata import VERSION
from packaging_policy import RUNTIME_ASSETS, QML_FILES, RUNTIME_SCRIPTS


def validate_release(directory: Path) -> list[Path]:
    app = directory / "PS3Presence"
    if not (app / "PS3Presence.exe").is_file():
        raise FileNotFoundError("PS3Presence.exe is missing")
    assets = app / "_internal" / "assets"
    actual_assets = {path.relative_to(assets).as_posix() for path in assets.rglob("*") if path.is_file()}
    if actual_assets != set(RUNTIME_ASSETS):
        raise ValueError(f"Runtime asset manifest mismatch: {actual_assets ^ set(RUNTIME_ASSETS)}")
    qml = app / "_internal" / "qml"
    if {path.name for path in qml.iterdir() if path.is_file()} != set(QML_FILES):
        raise ValueError("Runtime QML file manifest mismatch")
    for script in RUNTIME_SCRIPTS:
        if not (app / "_internal" / script).is_file():
            raise FileNotFoundError(f"Runtime autostart script missing: {script}")
    files = sorted(path for path in app.rglob("*") if path.is_file())
    private_parts = {".env", "logs", "auth.dat", "config.json", "observed_game_statuses.json", "game_statistics.sqlite3", "game_statistics.sqlite3-journal", "game_statistics.sqlite3-wal", "game_statistics.sqlite3-shm"}
    for path in files:
        relative = path.relative_to(app)
        if private_parts.intersection(relative.parts):
            raise ValueError(f"Private runtime data found: {relative}")
        name = path.name.casefold()
        if "webengine" in name or name.startswith(("avcodec-", "avformat-", "swresample-", "swscale-", "avutil-")):
            raise ValueError(f"Unused media/browser dependency found: {relative}")
        if name in {"qt6pdf.dll", "qpdf.dll", "ffmpegmediaplugin.dll", "windowsmediaplugin.dll"}:
            raise ValueError(f"Unused plugin found: {relative}")
    files.append(directory / "README.txt")
    if not files[-1].is_file():
        raise FileNotFoundError("Release README.txt is missing")
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_directory", type=Path)
    args = parser.parse_args()
    directory = args.release_directory.resolve()
    # The tool only writes generated artifacts beneath this project's releases.
    directory.relative_to((PROJECT_DIR / "releases").resolve())
    if directory == (PROJECT_DIR / "releases").resolve():
        raise ValueError("Choose a versioned release directory")
    files = validate_release(directory)
    archive = directory / f"PS3Presence-{VERSION}-win64-compact.zip"
    temporary = archive.with_suffix(".zip.tmp")
    if archive.exists() or temporary.exists():
        raise FileExistsError("Preserving an existing archive; use a fresh release folder")
    expected = {path.relative_to(directory).as_posix(): path.stat().st_size for path in files}
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in files:
            output.write(path, arcname=path.relative_to(directory).as_posix())
    with zipfile.ZipFile(temporary) as check:
        actual = {item.filename: item.file_size for item in check.infolist()}
        if actual != expected or check.testzip() is not None:
            raise ValueError("ZIP integrity or complete file list check failed")
    temporary.replace(archive)
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    (directory / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "zip_bytes": archive.stat().st_size,
                      "unpacked_bytes": sum(expected.values()), "files": len(files), "sha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
