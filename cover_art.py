"""Validated PSN artwork with a key-free GameTDB PS3 fallback.

Runs only in the bridge worker, never on the Qt UI thread. Cache files contain
public artwork/catalog data, not PSN credentials. Discord keeps a public URL.
"""
from __future__ import annotations

import io
import hashlib
import json
import re
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

import requests

from presence_parser import LegacyPresence
from settings_store import APP_DATA_DIR, _write_atomically

CATALOG_URL = "https://www.gametdb.com/ps3tdb.zip?LANG=EN"
ART_BASE = "https://art.gametdb.com/ps3/cover"
IMAGE_PROXY_URL = "https://wsrv.nl/"
CATALOG_TTL = 7 * 86400
COVER_TTL = 7 * 86400
MISS_TTL = 3600
NETWORK_RETRY_SECONDS = 60
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_XML = 24 * 1024 * 1024
MAX_LOOKUP_SECONDS = 30
SERIAL = re.compile(r"[A-Z]{4}\d{5}")
MAX_IMAGE_CACHE_BYTES = 64 * 1024 * 1024
CACHE_VERSION = 3


def local_cover_url(public_url: str | None, cache_dir: Path | None = None) -> str | None:
    if not public_url:
        return None
    directory = cache_dir if cache_dir is not None else APP_DATA_DIR / "covers"
    path = directory / (hashlib.sha256(public_url.encode("utf-8")).hexdigest() + ".img")
    try:
        return path.resolve().as_uri() if path.is_file() and path.stat().st_size > 0 else None
    except OSError:
        return None


def load_local_cover_index(cache_dir: Path | None = None) -> dict[str, str]:
    directory = cache_dir if cache_dir is not None else APP_DATA_DIR / "covers"
    result = {}
    try:
        cached = json.loads((directory / "resolved.json").read_text(encoding="utf-8"))
        if not isinstance(cached, dict):
            return result
        for key, entry in cached.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
                continue
            try:
                identity = json.loads(key)
            except (ValueError, TypeError):
                continue
            local = local_cover_url(entry["url"], directory)
            if isinstance(identity, list) and identity and isinstance(identity[0], str) and local:
                result[identity[0]] = local
    except (OSError, ValueError, TypeError):
        pass
    return result


def square_cover_url(source_url: str) -> str:
    query = urlencode(dict(url=source_url, w=512, h=512, fit="contain", cbg="00000000", output="png"))
    return f"{IMAGE_PROXY_URL}?{query}"


def normalize_title(title: str) -> str:
    title = re.sub(r"[™®©]", "", title)
    title = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"[^\W_]+", title))


def base_title(title: str) -> str:
    # Strip only a demo suffix, never numbers, subtitles or edition names.
    normalized = normalize_title(title)
    return re.sub(r"(?:\s+(?:(?:co op|multiplayer|single player|download|trial)\s+)?demo(?:\s+version)?)$",
                  "", normalized)


def serial_id(value: str | None) -> str:
    candidate = (value or "").upper().split("_", 1)[0].replace("-", "")
    return candidate if SERIAL.fullmatch(candidate) else ""


def artwork_regions(serial: str) -> tuple[str, ...]:
    region = {"E": "EN", "U": "US", "J": "JA", "A": "ZH", "H": "ZH"}.get(serial[2:3], "EN")
    return tuple(dict.fromkeys((region, "EN", "US")))[:2]


@dataclass(frozen=True)
class CatalogGame:
    serial: str
    titles: tuple[str, ...]


def parse_catalog(data: bytes) -> list[CatalogGame]:
    if len(data) > MAX_XML or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Invalid GameTDB XML")
    root = ElementTree.fromstring(data)
    result = []
    for game in root.findall("game"):
        serial = serial_id(game.findtext("id"))
        if not serial:
            continue
        titles = [locale.findtext("title", "") for locale in game.findall("locale")]
        # The name attribute can include dump/region qualifiers; localized
        # titles are the authoritative names for exact matching.
        if not any(titles):
            titles = [game.get("name", "")]
        result.append(CatalogGame(serial, tuple(dict.fromkeys(normalize_title(t) for t in titles if t))))
    if not result:
        raise ValueError("Empty GameTDB catalog")
    return result


class CoverResolver:
    def __init__(self, cache_dir: Path | None = None, *, session=None,
                 clock: Callable[[], float] = time.time, log: Callable[[str], None] = lambda _: None,
                 cancelled: Callable[[], bool] = lambda: False):
        self.cache_dir = cache_dir if cache_dir is not None else APP_DATA_DIR / "covers"
        self.clock, self.log = clock, log
        self.cancelled = cancelled
        self._deadline = float("inf")
        self._network_failed = False
        self._image_data: dict[str, bytes] = {}
        self._http_hosts: set[str] = set()
        self._last_response_status: int | None = None
        self.session = session if session is not None else requests.Session()
        # Artwork is public. Do not inherit .netrc credentials or a broken
        # environment proxy from unrelated applications.
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": "PS3Presence (PS3 cover lookup; https://www.gametdb.com)"})
        self._catalog: list[CatalogGame] | None = None
        self._catalog_next_check = 0.0
        self._catalog_attempt_at = -float("inf")
        self._proxy_retry_at = 0.0
        self._cache = {}
        try:
            data = json.loads((self.cache_dir / "resolved.json").read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cache = {key: value for key, value in data.items()
                               if isinstance(value, dict) and isinstance(value.get("at"), (int, float))
                               and (value.get("url") or value.get("version") == CACHE_VERSION)}
        except (OSError, ValueError):
            pass

    def close(self):
        self.session.close()

    def _get(self, url: str, limit: int) -> bytes | None:
        parsed = urlsplit(url)
        if parsed.scheme == "https" and parsed.hostname in self._http_hosts:
            return self._request(parsed._replace(scheme="http").geturl(), limit)
        previous_failure = self._network_failed
        data = self._request(url, limit)
        # Only GameTDB's public images/catalog can use plaintext fallback.
        # PSN credentials, endpoints and arbitrary URLs never take this route.
        if (data is None and self._last_response_status not in (404, 410) and parsed.scheme == "https"
                and parsed.hostname in ("www.gametdb.com", "art.gametdb.com")):
            fallback = parsed._replace(scheme="http").geturl()
            data = self._request(fallback, limit)
            if data or self._last_response_status in (404, 410):
                self._network_failed = previous_failure
            if data:
                self.log(f"GameTDB public download recovered over HTTP: {parsed.hostname}.")
        return data

    def _request(self, url: str, limit: int) -> bytes | None:
        self._last_response_status = None
        remaining = self._deadline - time.monotonic()
        if self.cancelled() or remaining <= 0:
            self._network_failed = True
            return None
        try:
            connect_timeout = min(3, remaining / 3)
            read_timeout = min(15 if urlsplit(url).path == "/ps3tdb.zip" else 5, remaining - connect_timeout)
            with self.session.get(url, timeout=(connect_timeout, read_timeout), stream=True) as response:
                self._last_response_status = response.status_code
                parsed = urlsplit(url)
                if (parsed.scheme == "http" and parsed.hostname in ("www.gametdb.com", "art.gametdb.com")
                        and (response.status_code == 200
                             or (parsed.hostname == "art.gametdb.com" and response.status_code in (404, 410)))):
                    self._http_hosts.add(parsed.hostname)
                if response.status_code != 200:
                    if response.status_code not in (404, 410):
                        self._network_failed = True
                        self.log(f"Artwork request failed: {urlsplit(url).hostname} (HTTP {response.status_code}).")
                    return None
                content = bytearray()
                for chunk in response.iter_content(65536):
                    if self.cancelled() or time.monotonic() >= self._deadline:
                        self._network_failed = True
                        return None
                    content.extend(chunk)
                    if len(content) > limit:
                        self._network_failed = True
                        return None
                return bytes(content)
        except requests.RequestException as error:
            self._network_failed = True
            self.log(f"Artwork request failed: {urlsplit(url).hostname} ({type(error).__name__}).")
            return None

    def _is_image(self, url: str) -> bool:
        try:
            parsed = urlsplit(url)
        except ValueError:
            return False
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        data = self._get(url, MAX_DOWNLOAD)
        valid = bool(data and (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")
                             or data.startswith((b"GIF87a", b"GIF89a"))
                             or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")))
        if valid:
            self._image_data[url] = data
        return valid

    def local_url(self, public_url: str | None) -> str | None:
        return local_cover_url(public_url, self.cache_dir)

    def _save_image(self, public_url: str, data: bytes) -> None:
        path = self.cache_dir / (hashlib.sha256(public_url.encode("utf-8")).hexdigest() + ".img")
        try:
            _write_atomically(path, data)
            files = [item for item in self.cache_dir.glob("*.img")
                     if re.fullmatch(r"[a-f0-9]{64}\.img", item.name) and not item.is_symlink()]
            files.sort(key=lambda item: item.stat().st_mtime)
            total = sum(item.stat().st_size for item in files)
            for item in files:
                if total <= MAX_IMAGE_CACHE_BYTES:
                    break
                if item != path:
                    size = item.stat().st_size
                    item.unlink()
                    total -= size
        except OSError:
            self.log("Artwork cache could not be saved; using the public image URL.")

    def _load_catalog(self) -> list[CatalogGame]:
        if self._catalog is not None and self.clock() < self._catalog_next_check:
            return self._catalog
        path = self.cache_dir / "ps3tdb.xml"
        cached = None
        try:
            cached = parse_catalog(path.read_bytes())
            if self.clock() - path.stat().st_mtime < CATALOG_TTL:
                self._catalog = cached
                self._catalog_next_check = path.stat().st_mtime + CATALOG_TTL
                return cached
        except (OSError, ValueError, ElementTree.ParseError):
            pass
        if self.clock() - self._catalog_attempt_at < NETWORK_RETRY_SECONDS:
            self._network_failed = True
            return cached or []
        self._catalog_attempt_at = self.clock()
        archive = self._get(CATALOG_URL, MAX_DOWNLOAD)
        if archive:
            try:
                with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                    entry = zipped.getinfo("ps3tdb.xml")
                    if entry.file_size > MAX_XML:
                        raise ValueError("GameTDB catalog is too large")
                    data = zipped.read(entry)
                self._catalog = parse_catalog(data)
                self._catalog_next_check = self.clock() + CATALOG_TTL
                try:
                    _write_atomically(path, data)
                except OSError:
                    pass
                return self._catalog
            except (ValueError, KeyError, OSError, RuntimeError, zipfile.BadZipFile, ElementTree.ParseError):
                pass
        if cached:
            self._catalog = cached
            self._catalog_next_check = self.clock() + NETWORK_RETRY_SECONDS
        self._network_failed = True
        self.log("GameTDB catalog unavailable; using cached artwork when possible.")
        return cached or []

    def _candidates(self, game: LegacyPresence) -> list[str]:
        serial = serial_id(game.title_id)
        result = [serial] if serial else []
        catalog = self._load_catalog()
        exact = normalize_title(game.title_name or "")
        # A known demo ID can identify the base title even when PSN appends
        # unusual demo text. Otherwise only the narrow suffix rule is used.
        names = {base_title(game.title_name or "")}
        for entry in catalog:
            if entry.serial == serial:
                names.update(entry.titles)
        matches = [entry for entry in catalog if exact in entry.titles or names.intersection(entry.titles)]
        region = serial[2:3]
        matches.sort(key=lambda entry: (exact not in entry.titles, entry.serial[2:3] != region,
                                       not entry.serial.startswith("B"), entry.serial))
        result.extend(entry.serial for entry in matches)
        return list(dict.fromkeys(result))[:4]

    def _public_url(self, source: str) -> str:
        parsed = urlsplit(source)
        if parsed.hostname in self._http_hosts:
            source = parsed._replace(scheme="http").geturl()
        if self.clock() >= self._proxy_retry_at:
            square = square_cover_url(source)
            if self._is_image(square):
                return square
            # If the image proxy refuses a valid source, use the original
            # public URL rather than persisting another broken link.
            self._proxy_retry_at = self.clock() + MISS_TTL
        return source

    def resolve(self, game: LegacyPresence, sony_url: str | None) -> str | None:
        self._deadline = time.monotonic() + MAX_LOOKUP_SECONDS
        self._network_failed = False
        self._image_data.clear()
        key = json.dumps([game.title_id, normalize_title(game.title_name or ""), sony_url], ensure_ascii=False)
        cached = self._cache.get(key)
        if isinstance(cached, dict):
            stamp, url = cached.get("at"), cached.get("url")
            if isinstance(stamp, (int, float)) and (url is None or isinstance(url, str)):
                ttl = COVER_TTL if url else cached.get("retry_after", NETWORK_RETRY_SECONDS)
                if isinstance(ttl, (int, float)) and 0 <= self.clock() - stamp < ttl:
                    if not url or self.local_url(url):
                        return url
                    # Older caches stored only URLs, not images. Verify and
                    # populate the local image instead of reusing a dead URL.
                    if self._is_image(url):
                        self._save_image(url, self._image_data[url])
                        return url
        result, provider = None, None
        image = None
        if sony_url and self._is_image(sony_url):
            image = self._image_data[sony_url]
            result, provider = self._public_url(sony_url), "PlayStation"
        else:
            for candidate in self._candidates(game):
                if self.cancelled() or time.monotonic() >= self._deadline:
                    self._network_failed = True
                    break
                for region in artwork_regions(candidate):
                    source = f"{ART_BASE}/{region}/{candidate}.jpg"
                    if self._is_image(source):
                        image = self._image_data[source]
                        result, provider = self._public_url(source), "GameTDB"
                        break
                if result:
                    break
        if self.cancelled():
            return None
        if result and image:
            self._save_image(result, image)
        self._cache[key] = dict(version=CACHE_VERSION, at=self.clock(), url=result,
                               retry_after=NETWORK_RETRY_SECONDS if self._network_failed else MISS_TTL)
        # Bound URL metadata; the small catalog is downloaded only on demand.
        self._cache = dict(sorted(self._cache.items(), key=lambda item: item[1].get("at", 0)
                                 if isinstance(item[1], dict) else 0)[-1000:])
        try:
            _write_atomically(self.cache_dir / "resolved.json", json.dumps(self._cache, ensure_ascii=False).encode("utf-8"))
        except OSError:
            pass
        if result:
            self.log(f"Cover resolved from {provider}: {game.title_name}")
        return result
