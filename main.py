from __future__ import annotations

import argparse
import sys
from typing import Any

from bridge import (
    LEGACY_PROFILE_FIELDS,
    PresenceBridge,
    discord_update_arguments,
    fetch_legacy_profile,
    get_legacy_profile_with_game_status,
    load_settings,
    resolve_ps3_cover_url,
    square_cover_url,
)
from presence_parser import LegacyPresence, extract_legacy_presences, select_active_ps3_game


def print_probe_result(online_id: str, payload: dict[str, Any]) -> LegacyPresence | None:
    profile = payload.get("profile") if isinstance(payload, dict) else None
    profile_status = profile.get("primaryOnlineStatus") if isinstance(profile, dict) else None
    presences = extract_legacy_presences(payload)

    print(f"PSN Online ID: {online_id}")
    print(f"Profile status: {profile_status or 'not returned'}")
    print(f"Presence records: {len(presences)}")

    if not presences:
        print("Result: the legacy endpoint returned no presence records.")
        return None

    for index, presence in enumerate(presences, start=1):
        print(f"Presence #{index}")
        print(f"  Online status: {presence.online_status or 'not returned'}")
        print(f"  Platform: {presence.platform or 'not returned'}")
        print(f"  Game: {presence.title_name or 'not returned'}")
        print(f"  Title ID: {presence.title_id or 'not returned'}")
        if presence.game_status:
            print(f"  Game status: {presence.game_status}")

    active_game = select_active_ps3_game(presences)
    if active_game:
        print(f"Result: PASS - PS3 detected, current game is {active_game.title_name!r}.")
    elif any(presence.is_ps3 and presence.is_online for presence in presences):
        print("Result: PARTIAL - PS3 is online, but PSN did not return a game title.")
    elif any(presence.is_ps3 for presence in presences):
        print("Result: PARTIAL - PS3 is present in the response, but it is reported offline.")
    else:
        print("Result: PS3 was not found in the legacy presence response.")
    return active_game


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PS3 legacy PSN presence probe and Discord Rich Presence bridge.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Query get_profile_legacy() once and print only platform/game fields; do not connect to Discord.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        settings = load_settings()
        if args.once:
            online_id, payload = fetch_legacy_profile(settings.npsso)
            print_probe_result(online_id, payload)
            return 0

        PresenceBridge(settings).run()
        return 0
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # Keep authentication/network errors concise and avoid dumping sensitive state.
        print(f"Runtime error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
