from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
TASK_NAME = "PS3 Discord Presence"


def _run_hidden(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Call Task Scheduler without briefly flashing a console window."""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        check=False,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def is_autostart_enabled() -> bool:
    result = _run_hidden(["schtasks.exe", "/Query", "/TN", TASK_NAME])
    return result.returncode == 0


def set_autostart_enabled(enabled: bool) -> None:
    if enabled and is_autostart_enabled():
        return
    if not enabled and not is_autostart_enabled():
        return
    script_name = "install_autostart.ps1" if enabled else "uninstall_autostart.ps1"
    arguments = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PROJECT_DIR / script_name)]
    if enabled:
        arguments.append("-NoStart")
        if getattr(sys, "frozen", False):
            arguments += ["-ExecutablePath", str(Path(sys.executable).resolve())]
    result = _run_hidden(arguments)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Windows Task Scheduler rejected the change.").strip()
        raise RuntimeError(detail)
