from __future__ import annotations

import ctypes
import json
import os
import time
from ctypes import POINTER, Structure, byref, c_char, cast
from ctypes import wintypes
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from localization import DEFAULT_LANGUAGE, normalize_language


APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PS3Presence"
CONFIG_FILE = APP_DATA_DIR / "config.json"
AUTH_FILE = APP_DATA_DIR / "auth.dat"
SCHEMA_VERSION = 2
CRYPTPROTECT_UI_FORBIDDEN = 0x1
DEFAULT_THEME_ID = "aurora"
VALID_THEME_IDS = {
    "botanical", "light", "oled", "terracotta", "indigo", "sakura", "aurora", "newyear",
}


class DataBlob(Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", POINTER(c_char))]


@dataclass(frozen=True, slots=True)
class StoredConfiguration:
    discord_client_id: str | None = None
    poll_interval: int | None = None
    large_image: str | None = None
    light_offsets: dict[str, tuple[int, int]] = field(default_factory=dict)
    theme_id: str = DEFAULT_THEME_ID
    language: str = DEFAULT_LANGUAGE


def is_new_year_theme_available(today: date | None = None) -> bool:
    current = today or date.today()
    return (current.month == 12 and current.day >= 10) or (current.month == 1 and current.day <= 20)


def normalize_theme_id(theme_id: object) -> str:
    if theme_id not in VALID_THEME_IDS:
        return DEFAULT_THEME_ID
    if theme_id == "newyear" and not is_new_year_theme_available():
        return DEFAULT_THEME_ID
    return str(theme_id)


def _blob(data: bytes) -> tuple[DataBlob, Any]:
    buffer = (c_char * len(data)).from_buffer_copy(data)
    return DataBlob(len(data), cast(buffer, POINTER(c_char))), buffer


def _crypt32() -> Any:
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    arguments = [
        POINTER(DataBlob), ctypes.c_wchar_p, POINTER(DataBlob), ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, POINTER(DataBlob),
    ]
    library.CryptProtectData.argtypes = arguments
    library.CryptProtectData.restype = wintypes.BOOL
    library.CryptUnprotectData.argtypes = arguments
    library.CryptUnprotectData.restype = wintypes.BOOL
    return library


def _free_blob(blob: DataBlob) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.LocalFree(cast(blob.pbData, ctypes.c_void_p))


def _protect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    destination = DataBlob()
    crypt32 = _crypt32()
    if not crypt32.CryptProtectData(byref(source), "PS3 Presence", None, None, None, CRYPTPROTECT_UI_FORBIDDEN, byref(destination)):
        raise OSError(ctypes.get_last_error(), "Windows could not protect PS3 Presence credentials.")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        _free_blob(destination)
        del source_buffer


def _unprotect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    destination = DataBlob()
    crypt32 = _crypt32()
    if not crypt32.CryptUnprotectData(byref(source), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, byref(destination)):
        raise OSError(ctypes.get_last_error(), "Windows could not unlock PS3 Presence credentials for this Windows user.")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        _free_blob(destination)
        del source_buffer


def _write_atomically(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", delete=False, dir=path.parent, prefix=f"{path.name}.", suffix=".tmp") as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def load_configuration() -> StoredConfiguration:
    if not CONFIG_FILE.exists():
        return StoredConfiguration()
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Saved application settings cannot be read.") from error
    if not isinstance(payload, dict):
        raise ValueError("Saved application settings are invalid.")
    client_id = payload.get("discord_client_id")
    poll_interval = payload.get("poll_interval")
    large_image = payload.get("large_image")
    raw_offsets = payload.get("light_offsets")
    raw_theme_id = payload.get("theme_id")
    light_offsets: dict[str, tuple[int, int]] = {}
    if isinstance(raw_offsets, dict):
        for key, value in raw_offsets.items():
            if isinstance(key, str) and isinstance(value, list) and len(value) == 2 and all(isinstance(item, int) for item in value):
                light_offsets[key] = (value[0], value[1])
    return StoredConfiguration(
        discord_client_id=client_id.strip() if isinstance(client_id, str) and client_id.strip() else None,
        poll_interval=poll_interval if isinstance(poll_interval, int) else None,
        large_image=large_image.strip() if isinstance(large_image, str) and large_image.strip() else None,
        light_offsets=light_offsets,
        theme_id=normalize_theme_id(raw_theme_id),
        language=normalize_language(payload.get("language")),
    )


def save_configuration(configuration: StoredConfiguration) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "discord_client_id": configuration.discord_client_id or "",
        "poll_interval": configuration.poll_interval,
        "large_image": configuration.large_image or "",
        "light_offsets": {key: list(value) for key, value in configuration.light_offsets.items()},
        "theme_id": normalize_theme_id(configuration.theme_id),
        "language": normalize_language(configuration.language),
    }
    _write_atomically(CONFIG_FILE, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def save_light_offset(index: int, x: int, y: int) -> dict[str, tuple[int, int]]:
    """Persist a per-lamp visual calibration without touching credentials."""
    configuration = load_configuration()
    offsets = dict(configuration.light_offsets)
    offsets[str(index)] = (int(x), int(y))
    save_configuration(replace(configuration, light_offsets=offsets))
    return offsets


def save_theme(theme_id: str) -> str:
    """Persist the selected visual theme without changing other settings."""
    normalized = normalize_theme_id(theme_id)
    configuration = load_configuration()
    save_configuration(replace(configuration, theme_id=normalized))
    return normalized


def save_language(language: str) -> str:
    normalized = normalize_language(language)
    save_configuration(replace(load_configuration(), language=normalized))
    return normalized


def load_npsso() -> str | None:
    payload = _load_auth_payload()
    value = payload.get("npsso")
    return value.strip() if isinstance(value, str) and value.strip() else None


def load_npsso_expires_at() -> float | None:
    """Return Sony's known NPSSO expiry time, when it was pasted as JSON."""
    payload = _load_auth_payload()
    value = payload.get("expires_at")
    return float(value) if isinstance(value, (int, float)) and value > 0 else None


def _load_auth_payload() -> dict[str, Any]:
    if not AUTH_FILE.exists():
        return {}
    try:
        payload = json.loads(_unprotect(AUTH_FILE.read_bytes()).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Saved PSN credential cannot be read for this Windows user.") from error
    return payload if isinstance(payload, dict) else {}


def save_npsso(npsso: str, expires_in: int | None = None) -> None:
    value = npsso.strip()
    if not value:
        raise ValueError("NPSSO cannot be empty.")
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "npsso": value}
    if expires_in is not None and expires_in > 0:
        payload["expires_at"] = time.time() + expires_in
    _write_atomically(AUTH_FILE, _protect(json.dumps(payload, separators=(",", ":")).encode("utf-8")))
