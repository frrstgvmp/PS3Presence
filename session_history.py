"""Observed sessions, persisted in the same transaction as aggregate playtime."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from time_format import format_playtime, format_russian_date
from localization import translate


HISTORY_LIMIT = 100
END_LABELS = {
    "idle": "Сессия завершена", "game_changed": "Смена игры",
    "account_changed": "Смена аккаунта", "stopped": "Программа остановлена",
    "closed": "Программа закрыта", "interrupted": "Прервана · последнее сохранённое наблюдение",
}


@dataclass
class SessionRecord:
    session_id: str
    account: str
    game_key: str
    title: str
    cover: str
    started_at: int
    last_seen_at: int
    ended_at: int | None
    total_seconds: float
    end_reason: str
    order: int


class SessionHistory:
    def __init__(self):
        self.records: dict[str, SessionRecord] = {}
        self.active_id: str | None = None
        self.dirty: set[str] = set()
        self._sequence = 0

    def load(self, db):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='game_sessions'").fetchone():
            return
        accounts = {}
        for order, *values in db.execute("SELECT rowid,session_id,account,game_key,title,cover,started_at,"
                "last_seen_at,ended_at,total_seconds,end_reason FROM game_sessions ORDER BY account,rowid DESC"):
            self._sequence = max(self._sequence, order)
            record = SessionRecord(*values, order=order)
            accounts[record.account] = accounts.get(record.account, 0) + 1
            if accounts[record.account] > HISTORY_LIMIT:
                continue
            if not all(isinstance(value, str) for value in (record.session_id, record.account,
                    record.game_key, record.title, record.cover, record.end_reason)):
                raise ValueError("Некорректная запись истории сессий")
            for timestamp in (record.started_at, record.last_seen_at, record.ended_at):
                if timestamp is not None:
                    if not isinstance(timestamp, int) or timestamp < 0:
                        raise ValueError("Некорректная дата истории сессий")
                    try:
                        datetime.fromtimestamp(timestamp)
                    except (ValueError, OSError, OverflowError) as error:
                        raise ValueError("Некорректная дата истории сессий") from error
            if (record.started_at is None or record.last_seen_at is None
                    or not isinstance(record.total_seconds, (int, float))
                    or not math.isfinite(record.total_seconds) or record.total_seconds < 0):
                raise ValueError("Некорректная длительность истории сессий")
            # An unclosed checkpoint belongs to a previous process. Never add
            # offline time or pretend the actual game exit was observed.
            if record.ended_at is None:
                record.ended_at = record.last_seen_at
                record.end_reason = "interrupted"
                self.dirty.add(record.session_id)
            self.records[record.session_id] = record

    def start(self, account, game_key, title, cover, now):
        self._sequence += 1
        session_id = str(uuid4())
        self.records[session_id] = SessionRecord(session_id, account, game_key, title, cover,
            now, now, None, 0.0, "", self._sequence)
        self.active_id = session_id
        self.dirty.add(session_id)

    def add_time(self, seconds, now):
        if self.active_id is not None:
            record = self.records[self.active_id]
            record.total_seconds += seconds
            record.last_seen_at = now
            self.dirty.add(record.session_id)

    def confirm(self, title, cover, now):
        if self.active_id is not None:
            record = self.records[self.active_id]
            record.title, record.cover, record.last_seen_at = title, cover, now
            self.dirty.add(record.session_id)

    def finish(self, now, reason):
        if self.active_id is not None:
            record = self.records[self.active_id]
            record.ended_at, record.end_reason = now, reason
            self.dirty.add(record.session_id)
            self.active_id = None

    def write(self, db):
        db.execute("CREATE TABLE IF NOT EXISTS game_sessions (session_id TEXT PRIMARY KEY, "
            "account TEXT NOT NULL, game_key TEXT NOT NULL, title TEXT NOT NULL, cover TEXT NOT NULL, "
            "started_at INTEGER NOT NULL, last_seen_at INTEGER NOT NULL, ended_at INTEGER, "
            "total_seconds REAL NOT NULL CHECK(total_seconds>=0), end_reason TEXT NOT NULL)")
        db.execute("CREATE INDEX IF NOT EXISTS game_sessions_account ON game_sessions(account)")
        for session_id in sorted(self.dirty, key=lambda key: self.records[key].order):
            record = self.records[session_id]
            db.execute("INSERT INTO game_sessions VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET title=excluded.title,cover=excluded.cover,"
                "last_seen_at=excluded.last_seen_at,ended_at=excluded.ended_at,"
                "total_seconds=excluded.total_seconds,end_reason=excluded.end_reason",
                (record.session_id, record.account, record.game_key, record.title, record.cover,
                 record.started_at, record.last_seen_at, record.ended_at, record.total_seconds, record.end_reason))

    def mark_saved(self):
        self.dirty.clear()
        accounts = {}
        for record in sorted(self.records.values(), key=lambda record: -record.order):
            accounts[record.account] = accounts.get(record.account, 0) + 1
            if accounts[record.account] > HISTORY_LIMIT and record.session_id != self.active_id:
                del self.records[record.session_id]

    def latest_starts(self, account):
        """Raw start times of the latest recorded session for each game."""
        latest = {}
        for record in self.records.values():
            if record.account == account:
                candidate = (record.order, record.started_at)
                if candidate > latest.get(record.game_key, (-1, 0)):
                    latest[record.game_key] = candidate
        return {key: value[1] for key, value in latest.items()}

    def rows(self, account, paused, language="ru"):
        result = []
        records = sorted((record for record in self.records.values() if record.account == account),
                         key=lambda record: -record.order)[:HISTORY_LIMIT]
        for record in records:
            current = record.session_id == self.active_id
            result.append(dict(sessionKey=record.session_id, gameKey=record.game_key, title=record.title, coverUrl=record.cover,
                playtime=format_playtime(record.total_seconds), totalSeconds=record.total_seconds,
                startedAt=format_russian_date(record.started_at, include_seconds=True, language=language),
                endedAt=format_russian_date(record.ended_at, include_seconds=True, language=language) if record.ended_at is not None else "",
                state=translate(("Подсчёт приостановлен · нет данных PSN" if paused else "Сейчас в игре") if current else END_LABELS.get(record.end_reason, "Сессия завершена"), language),
                isCurrent=current, isPaused=current and paused))
        return result
