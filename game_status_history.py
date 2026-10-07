from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from presence_parser import LegacyPresence


SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _game_key(game: LegacyPresence) -> str:
    if game.title_id:
        return game.title_id
    return f"unknown:{(game.title_name or 'unknown').casefold()}"


def _load_database(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "games": {}}

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), dict):
        raise ValueError(f"Invalid game-status database: {path}")
    return payload


def record_game_observation(
    game: LegacyPresence,
    path: Path,
    *,
    observed_at: str | None = None,
) -> None:
    """Record a game and each distinct PSN gameStatus without any account data."""
    timestamp = observed_at or _utc_now()
    payload = _load_database(path)
    games: dict[str, Any] = payload["games"]
    key = _game_key(game)

    entry = games.get(key)
    if not isinstance(entry, dict):
        entry = {
            "title_id": game.title_id,
            "title_name": game.title_name,
            "platform": game.platform,
            "first_seen_at": timestamp,
            "last_seen_at": timestamp,
            "without_status_observations": 0,
            "statuses": [],
        }
        games[key] = entry

    entry["title_name"] = game.title_name
    entry["platform"] = game.platform
    entry["last_seen_at"] = timestamp

    if game.game_status:
        statuses = entry.setdefault("statuses", [])
        matching = next(
            (status for status in statuses if isinstance(status, dict) and status.get("text") == game.game_status),
            None,
        )
        if matching is None:
            statuses.append(
                {
                    "text": game.game_status,
                    "first_seen_at": timestamp,
                    "last_seen_at": timestamp,
                    "observations": 1,
                }
            )
        else:
            matching["last_seen_at"] = timestamp
            matching["observations"] = int(matching.get("observations", 0)) + 1
    else:
        entry["without_status_observations"] = int(entry.get("without_status_observations", 0)) + 1

    payload["schema_version"] = SCHEMA_VERSION
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
