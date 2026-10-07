"""Keep unrelated host tools' native DLLs out of this application's process."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_DLL_HANDLES: list[object] = []
_PREPARED = False


def clean_native_path(value: str) -> str:
    """Exclude Codex's document/image helper DLL folders, not the Python runtime."""
    kept = []
    for entry in value.split(os.pathsep):
        normalized = entry.strip().strip('"').replace("\\", "/").casefold()
        if "/codex-runtimes/" in normalized and "/dependencies/native/" in normalized + "/":
            continue
        kept.append(entry)
    return os.pathsep.join(kept)


def prepare_native_libraries() -> None:
    """Run before Qt/SSL imports; only the current process's environment changes."""
    global _PREPARED
    if _PREPARED or os.name != "nt":
        return
    _PREPARED = True
    directories = [Path(sys.base_prefix) / "DLLs", Path(sys.base_prefix)]
    if getattr(sys, "frozen", False):
        resource_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        directories.extend([
            resource_dir / "PySide6", resource_dir / "shiboken6",
            resource_dir / "lib" / "PySide6", resource_dir / "lib" / "shiboken6",
        ])
    else:
        packages = Path(sys.prefix) / "Lib" / "site-packages"
        directories.extend([packages / "PySide6", packages / "shiboken6"])
    existing = []
    for directory in directories:
        if directory.is_dir() and str(directory) not in existing:
            existing.append(str(directory))
            # Retain the handles: garbage collection would otherwise unregister
            # these directories before Windows loads a delayed Qt dependency.
            _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    os.environ["PATH"] = os.pathsep.join(existing + [clean_native_path(os.environ.get("PATH", ""))])
