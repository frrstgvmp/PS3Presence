from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class LegacyPresence:
    online_status: str | None
    platform: str | None
    title_name: str | None
    title_id: str | None
    game_status: str | None
    title_icon_url: str | None

    @property
    def is_online(self) -> bool:
        return (self.online_status or "").casefold() not in {"", "offline"}

    @property
    def is_ps3(self) -> bool:
        normalized = "".join(character for character in (self.platform or "").upper() if character.isalnum())
        return normalized in {"PS3", "PLAYSTATION3"}


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _find_string(value: Any, keys: Iterable[str]) -> str | None:
    """Find a named string recursively while preferring fields on the current object."""
    wanted = tuple(keys)
    if isinstance(value, dict):
        for key in wanted:
            result = _non_empty_string(value.get(key))
            if result:
                return result
        for nested in value.values():
            result = _find_string(nested, wanted)
            if result:
                return result
    elif isinstance(value, list):
        for nested in value:
            result = _find_string(nested, wanted)
            if result:
                return result
    return None


def extract_legacy_presences(payload: dict[str, Any]) -> list[LegacyPresence]:
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        return []

    raw_presences = profile.get("presences")
    if not isinstance(raw_presences, list):
        return []

    parsed: list[LegacyPresence] = []
    for raw_presence in raw_presences:
        if not isinstance(raw_presence, dict):
            continue
        parsed.append(
            LegacyPresence(
                online_status=_find_string(raw_presence, ("onlineStatus",)),
                platform=_find_string(raw_presence, ("platform", "launchPlatform")),
                title_name=_find_string(raw_presence, ("titleName", "npTitleName")),
                title_id=_find_string(raw_presence, ("npTitleId", "titleId")),
                game_status=_find_string(raw_presence, ("gameStatus",)),
                title_icon_url=_find_string(raw_presence, ("npTitleIconUrl", "titleIconUrl", "iconUrl")),
            )
        )
    return parsed


def select_active_ps3_game(presences: Iterable[LegacyPresence]) -> LegacyPresence | None:
    candidates = [presence for presence in presences if presence.is_ps3 and presence.is_online]
    return next((presence for presence in candidates if presence.title_name), None)
