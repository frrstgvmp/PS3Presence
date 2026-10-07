"""Explicit runtime asset manifest and Qt module selection for portable builds."""
from __future__ import annotations

from pathlib import Path, PurePosixPath

RUNTIME_ASSETS = (
    "botanical-theme.png", "botanical-cannabis-theme.png", "newyear-theme.png", "ps3-presence.ico",
    "dualshock3.png", "presence-mark.svg", "about-pacman.gif",
    "discord-mark-white.svg", "discord-mark-black.svg",
    "github-mark-white.svg", "github-mark-black.svg",
    *(f"newyear/pcm/sound{index}.wav" for index in range(1, 37)),
)
QML_FILES = ("Main.qml", "Avatar.qml", "Snowfall.qml", "LeafFall.qml", "FallingPhrase.qml", "ConnectionIndicator.qml", "GameStatisticsDialog.qml")
RUNTIME_SCRIPTS = ("install_autostart.ps1", "uninstall_autostart.ps1")


def runtime_data(project_dir: Path) -> list[tuple[str, str]]:
    files = [(project_dir / "assets" / name, str(PurePosixPath("assets") / PurePosixPath(name).parent))
             for name in RUNTIME_ASSETS]
    files += [(project_dir / "qml" / name, "qml") for name in QML_FILES]
    files += [(project_dir / name, ".") for name in RUNTIME_SCRIPTS]
    for source, _ in files:
        if not source.is_file():
            raise FileNotFoundError(f"Required runtime asset is missing: {source}")
    return [(str(source), destination) for source, destination in files]


def qml_module_is_used(relative_path: str | Path, *, is_directory: bool = False) -> bool:
    parts = PurePosixPath(str(relative_path).replace("\\", "/")).parts
    if not parts or ".." in parts or PurePosixPath(*parts).is_absolute():
        return False
    if parts[-1].endswith(".qmltypes") or "designer" in parts:
        return False
    if parts[0] in {"QML", "QtQml"}:
        return True
    if parts[0] != "QtQuick" or len(parts) < 2:
        return False
    if len(parts) == 2 and not is_directory:
        return True
    if parts[1] in {"Layouts", "Templates", "Window"}:
        return True
    if parts[1] != "Controls" or len(parts) < 3:
        return False
    return (len(parts) == 3 and not is_directory) or parts[2] in {"Basic", "impl"}


def runtime_data_is_used(destination: str) -> bool:
    """Keep databases but omit unused country catalogs and Qt translations."""
    parts = PurePosixPath(destination.replace("\\", "/")).parts
    if parts[:2] == ("pycountry", "locales"):
        return False
    if parts[:2] == ("PySide6", "translations"):
        return parts[-1].endswith(("_ru.qm", "_en.qm"))
    return True
