"""Copy unchanged upstream notices into the portable runtime directory."""
from __future__ import annotations

import argparse
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
PACKAGES = (
    "PSNAWP", "pypresence", "python-dotenv", "pycountry", "pyrate-limiter",
    "requests", "typing-extensions", "urllib3", "idna", "certifi",
    "charset-normalizer", "PyInstaller", "setuptools",
)


def prepare(directory: Path) -> int:
    directory = directory.resolve()
    directory.relative_to((PROJECT_DIR / "releases").resolve())
    app = directory / "PS3Presence"
    if not (app / "PS3Presence.exe").is_file():
        raise FileNotFoundError("Build PS3Presence.exe before preparing notices")
    output = app / "_internal" / "licenses"
    for source in (PROJECT_DIR / "packaging" / "licenses").rglob("*"):
        if source.is_file():
            destination = output / source.relative_to(PROJECT_DIR / "packaging" / "licenses")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError("Python runtime LICENSE.txt is missing")
    (output / "Python").mkdir(parents=True, exist_ok=True)
    shutil.copy2(python_license, output / "Python" / "LICENSE.txt")
    for name in PACKAGES:
        package = distribution(name)
        found = 0
        for entry in package.files or ():
            if ".dist-info" not in str(entry) or not entry.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
                continue
            destination = output / f"{package.metadata['Name']}-{package.version}" / entry.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(package.locate_file(entry), destination)
            found += 1
        if not found:
            raise FileNotFoundError(f"No upstream license found for {name}")
    return sum(path.is_file() for path in output.rglob("*"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_directory", type=Path)
    args = parser.parse_args()
    print(f"Prepared {prepare(args.release_directory)} third-party notice files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
