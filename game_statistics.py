"""Local observed playtime; no Qt, PSN calls, credentials, or offline backfill."""
from __future__ import annotations

import sqlite3
import time
import math
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Callable

from presence_parser import LegacyPresence
from session_history import SessionHistory
from time_format import format_playtime, format_russian_date


SCHEMA_VERSION = 1
FLUSH_INTERVAL = 15
MAX_TICK_GAP = 15  # Never count a suspended computer or a blocked event loop.


def _legacy_collection_start(path: Path, earliest_activity: int) -> int:
    # Windows exposes file birth time. Do not use POSIX ctime (metadata changes).
    birth = getattr(path.stat(), "st_birthtime", None)
    return min(int(birth), earliest_activity) if birth is not None and birth > 0 else earliest_activity


def _validate_timestamp(value: object) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError("Некорректная дата статистики игры")
    try:
        datetime.fromtimestamp(value)
    except (OSError, OverflowError, ValueError) as error:
        raise ValueError("Некорректная дата статистики игры") from error


class GameTimeTracker:
    def __init__(self, path: Path | None, *, clock: Callable[[], float] = time.monotonic,
                 wall_clock: Callable[[], float] = time.time, stale_after: float = 90):
        self.path = path
        self.clock, self.wall_clock = clock, wall_clock
        self.stale_after = max(30, stale_after)
        self._rows: dict[tuple[str, str], dict] = {}
        self._pending: dict[tuple[str, str], dict] = {}
        self._identity: tuple[str, str] | None = None
        self.account = ""
        self.paused = True
        self._tick_at = self._confirmed_at = self._flushed_at = self._session_at = clock()
        self._session_base = 0.0
        self._collection_started_at: int | None = None
        self._history = SessionHistory()
        if path is not None and path.exists():
            # Viewing an existing database does not create or modify it.
            with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                    raise ValueError("Неизвестная версия базы статистики")
                for account, key, title, cover, seconds, sessions, last_played in db.execute(
                        "SELECT account, game_key, title, cover, total_seconds, sessions, last_played FROM games"):
                    if (not all(isinstance(value, str) for value in (account, key, title, cover))
                            or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0
                            or not isinstance(sessions, int) or sessions < 0
                            or not isinstance(last_played, int)):
                        raise ValueError("Некорректная статистика игры")
                    _validate_timestamp(last_played)
                    self._rows[(account, key)] = dict(account=account, game_key=key, title=title,
                        cover=cover, total_seconds=seconds, sessions=sessions, last_played=last_played)
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='statistics_metadata'").fetchone():
                    started = db.execute("SELECT value FROM statistics_metadata WHERE key='collection_started_at'").fetchone()
                    if started is not None:
                        _validate_timestamp(started[0])
                        self._collection_started_at = started[0]
                self._history.load(db)
            if self._rows:
                self.account = max(self._rows.values(), key=lambda row: row["last_played"])["account"]
                if self._collection_started_at is None:
                    self._collection_started_at = _legacy_collection_start(path,
                        min(row["last_played"] for row in self._rows.values()))

    @property
    def collection_started_date(self) -> str:
        return self.format_collection_started_date()

    def format_collection_started_date(self, language: str = "ru") -> str:
        return format_russian_date(self._collection_started_at, language=language) if self._collection_started_at is not None else ""

    @property
    def session_elapsed(self) -> str:
        if self._identity is None:
            return "00:00:00"
        return format_playtime(self._session_base + max(0, self.clock() - self._session_at))

    def advance(self) -> None:
        now = self.clock()
        previous, self._tick_at = self._tick_at, now
        delta = now - previous
        if delta > MAX_TICK_GAP or delta < 0:
            self.paused = True
            return
        if not self.paused and self._identity is not None:
            seconds = max(0, min(now, self._confirmed_at + self.stale_after) - previous)
            if seconds:
                row = self._rows[self._identity]
                row["total_seconds"] += seconds
                row["last_played"] = int(self.wall_clock())
                pending = self._pending.setdefault(self._identity, {"seconds": 0.0, "sessions": 0})
                pending["seconds"] += seconds
                self._history.add_time(seconds, int(self.wall_clock()))
            if now >= self._confirmed_at + self.stale_after:
                self.paused = True

    def observe(self, game: LegacyPresence | None, account: str | None, cover: str | None = None,
                *, started_at: int | None = None, confirmed_idle: bool = False, end_reason: str = "idle") -> bool:
        self.advance()
        if account:
            if account.casefold() != self.account:
                self.finish_session("account_changed")
            self.account = account.casefold()
        if not game or not game.is_online or not game.is_ps3 or not game.title_name or not account:
            self.paused = True
            if confirmed_idle:
                self.finish_session(end_reason)
            return False
        key = (account.casefold(), game.title_id or "unknown:" + game.title_name.casefold())
        if self._collection_started_at is None:
            self._collection_started_at = int(self.wall_clock())
        new_session = key != self._identity
        row = self._rows.setdefault(key, dict(account=key[0], game_key=key[1], title=game.title_name,
            cover="", total_seconds=0.0, sessions=0, last_played=int(self.wall_clock())))
        row["title"] = game.title_name
        row["cover"] = cover or row["cover"] or game.title_icon_url or ""
        row["last_played"] = int(self.wall_clock())
        pending = self._pending.setdefault(key, {"seconds": 0.0, "sessions": 0})
        if new_session:
            self._history.finish(int(self.wall_clock()), "game_changed")
            row["sessions"] += 1
            pending["sessions"] += 1
            self._session_at = self.clock()
            self._session_base = max(0, self.wall_clock() - started_at) if started_at is not None else 0.0
            self._history.start(key[0], key[1], row["title"], row["cover"], int(self.wall_clock()))
        self._history.confirm(row["title"], row["cover"], int(self.wall_clock()))
        self._identity = key
        self._confirmed_at = self.clock()
        self.paused = False
        return new_session

    def rows(self, language: str = "ru") -> list[dict]:
        result = []
        last_starts = self._history.latest_starts(self.account)
        for key, row in self._rows.items():
            if key[0] != self.account:
                continue
            # Older/imported games may not have a retained session record.
            last_launch = last_starts.get(key[1], row["last_played"])
            result.append(dict(gameKey=key[1], title=row["title"], coverUrl=row["cover"],
                playtime=format_playtime(row["total_seconds"]), totalSeconds=row["total_seconds"],
                sessionCount=row["sessions"], isCurrent=key == self._identity and not self.paused,
                isPaused=key == self._identity and self.paused,
                lastPlayed=format_russian_date(last_launch, include_time=True, language=language),
                lastPlayedAt=last_launch))
        return sorted(result, key=lambda row: (-row["totalSeconds"], row["title"].casefold(), row["gameKey"]))

    def flush(self, *, force: bool = False) -> bool:
        now = self.clock()
        if (not self._pending and not self._history.dirty) or (not force and now - self._flushed_at < FLUSH_INTERVAL):
            return False
        self._flushed_at = now  # Bound automatic retries too, without dropping deltas.
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.25)) as db, db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, SCHEMA_VERSION):
                    raise ValueError("Неизвестная версия базы статистики")
                db.execute("CREATE TABLE IF NOT EXISTS games (account TEXT NOT NULL, game_key TEXT NOT NULL, "
                    "title TEXT NOT NULL, cover TEXT NOT NULL, total_seconds REAL NOT NULL CHECK(total_seconds>=0), "
                    "sessions INTEGER NOT NULL CHECK(sessions>=0), last_played INTEGER NOT NULL, "
                    "PRIMARY KEY(account,game_key))")
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                # Additive, version-1-compatible metadata: older EXEs keep their
                # seven-column game upserts working and cannot reset the date.
                db.execute("CREATE TABLE IF NOT EXISTS statistics_metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
                if self._collection_started_at is not None:
                    db.execute("INSERT INTO statistics_metadata VALUES ('collection_started_at', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=MIN(statistics_metadata.value, excluded.value)",
                        (self._collection_started_at,))
                for key, pending in self._pending.items():
                    row = self._rows[key]
                    db.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?) ON CONFLICT(account,game_key) DO UPDATE SET "
                        "title=excluded.title, cover=excluded.cover, "
                        "total_seconds=games.total_seconds+excluded.total_seconds, sessions=games.sessions+excluded.sessions, "
                        "last_played=excluded.last_played", (*key, row["title"], row["cover"],
                        pending["seconds"], pending["sessions"], row["last_played"]))
                self._history.write(db)
        # Only forget deltas after the complete transaction commits successfully.
        self._pending.clear()
        self._history.mark_saved()
        self._flushed_at = now
        return True

    def close(self) -> None:
        self.advance()
        self.finish_session("closed")
        self.flush(force=True)

    def finish_session(self, reason: str) -> None:
        self._history.finish(int(self.wall_clock()), reason)
        self._identity = None
        self.paused = True

    def history_rows(self, language: str = "ru") -> list[dict]:
        return self._history.rows(self.account, self.paused, language=language)
