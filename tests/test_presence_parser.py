from __future__ import annotations

import json
import tempfile
import time
import unittest
from unittest.mock import Mock
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from pypresence.payloads import Payload
from pypresence.types import StatusDisplayType

from game_status_history import record_game_observation
from main import (
    LEGACY_PROFILE_FIELDS,
    discord_update_arguments,
    get_legacy_profile_with_game_status,
    resolve_ps3_cover_url,
    square_cover_url,
)
from bridge import BridgePhase, BridgeSettings, BridgeSnapshot, PresenceBridge, extract_profile_avatar, refresh_token_expiration
from presence_parser import LegacyPresence, extract_legacy_presences, select_active_ps3_game


class LegacyPresenceParserTests(unittest.TestCase):
    def test_selects_largest_public_psn_avatar(self):
        payload = {"profile": {"avatarUrls": [
            {"size": "s", "avatarUrl": "https://example.invalid/s.png"},
            {"size": "l", "avatarUrl": "https://example.invalid/l.png"},
            {"size": "m", "avatarUrl": "https://example.invalid/m.png"},
        ]}}
        self.assertEqual(extract_profile_avatar(payload), "https://example.invalid/l.png")

    def test_reads_profile_picture_when_psn_omits_avatar_urls(self):
        payload = {"profile": {"personalDetail": {"profilePictureUrls": [
            {"size": "m", "profilePictureUrl": "https://example.invalid/medium.jpg"},
            {"size": "xl", "profilePictureUrl": "https://example.invalid/large.jpg"},
        ]}}}
        self.assertEqual(extract_profile_avatar(payload), "https://example.invalid/large.jpg")

    def test_prefers_the_psn_avatar_over_profile_picture(self):
        payload = {"profile": {
            "avatarUrls": [{"size": "l", "avatarUrl": "https://example.invalid/legacy-avatar.jpg"}],
            "personalDetail": {"profilePictureUrls": [
                {"size": "l", "profilePictureUrl": "https://example.invalid/psn-profile-picture.jpg"},
            ]},
        }}
        self.assertEqual(extract_profile_avatar(payload), "https://example.invalid/legacy-avatar.jpg")

    def test_missing_or_invalid_avatars_are_optional(self):
        for payload in ({}, {"profile": None}, {"profile": {"avatarUrls": None}}, {"profile": {"avatarUrls": [None, {}, {"avatarUrl": "file:///secret.png"}, {"avatarUrl": "https://"}]}}):
            self.assertIsNone(extract_profile_avatar(payload))

    def test_bridge_preserves_avatar_during_retry_without_leaking_to_other_identity(self):
        snapshots = []
        bridge = PresenceBridge(BridgeSettings("test", "client", 30, None), on_status=snapshots.append)
        bridge._avatar_online_id = "ExampleUser"
        bridge._avatar_url = "https://example.invalid/avatar.png"
        bridge._publish(BridgeSnapshot(BridgePhase.IDLE, "idle", "ExampleUser"))
        bridge._publish(BridgeSnapshot(BridgePhase.WAITING_FOR_PSN, "retry", "ExampleUser"))
        bridge._publish(BridgeSnapshot(BridgePhase.IDLE, "idle", "OtherUser"))
        self.assertEqual(snapshots[0].avatar_url, bridge._avatar_url)
        self.assertEqual(snapshots[1].avatar_url, bridge._avatar_url)
        self.assertIsNone(snapshots[2].avatar_url)

    def test_reads_only_refresh_token_expiration_metadata(self) -> None:
        class FakeAuthenticator:
            refresh_token_expiration_time = time.time() + 60

        class FakePsn:
            authenticator = FakeAuthenticator()

        result = refresh_token_expiration(FakePsn())  # type: ignore[arg-type]

        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreater(result, time.time())

    def test_legacy_request_explicitly_includes_game_status(self) -> None:
        class FakeResponse:
            def json(self) -> dict[str, object]:
                return {"profile": {}}

        class FakeAuthenticator:
            def get(self, **kwargs: object) -> FakeResponse:
                self.kwargs = kwargs
                return FakeResponse()

        class FakeClient:
            online_id = "ExampleUser"
            authenticator = FakeAuthenticator()

        result = get_legacy_profile_with_game_status(FakeClient())

        self.assertEqual(result, {"profile": {}})
        self.assertIn("gameStatus", LEGACY_PROFILE_FIELDS)
        self.assertIn("gameStatus", FakeClient.authenticator.kwargs["params"]["fields"])  # type: ignore[index]

    def test_records_unique_game_status_history(self) -> None:
        base_game = LegacyPresence(
            online_status="online",
            platform="PS3",
            title_name="Example Game",
            title_id="BCES00001_00",
            game_status=None,
            title_icon_url=None,
        )
        status_game = LegacyPresence(
            online_status="online",
            platform="PS3",
            title_name="Example Game",
            title_id="BCES00001_00",
            game_status="In multiplayer lobby",
            title_icon_url=None,
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            record_game_observation(base_game, path, observed_at="2026-09-02T10:00:00Z")
            record_game_observation(status_game, path, observed_at="2026-09-02T10:01:00Z")
            record_game_observation(status_game, path, observed_at="2026-09-02T10:02:00Z")
            payload = json.loads(path.read_text(encoding="utf-8"))

        entry = payload["games"]["BCES00001_00"]
        self.assertEqual(entry["without_status_observations"], 1)
        self.assertEqual(entry["statuses"][0]["text"], "In multiplayer lobby")
        self.assertEqual(entry["statuses"][0]["observations"], 2)
        self.assertEqual(entry["statuses"][0]["last_seen_at"], "2026-09-02T10:02:00Z")

    def test_discord_arguments_do_not_repeat_platform_as_state(self) -> None:
        game = LegacyPresence(
            online_status="online",
            platform="PS3",
            title_name="inFamous",
            title_id="BCES00609_00",
            game_status=None,
            title_icon_url=None,
        )

        arguments = discord_update_arguments(game, 123, None)

        self.assertEqual(arguments["details"], "inFamous")
        self.assertNotIn("state", arguments)

    def test_discord_compact_status_uses_game_title_and_keeps_rich_presence(self) -> None:
        for title in ("inFamous", "inFamous 2", None):
            with self.subTest(title=title):
                game = LegacyPresence("online", "PS3", title, "BCES00609_00",
                                      "In multiplayer lobby", None)
                arguments = discord_update_arguments(game, 123, "cover-key")
                self.assertIs(arguments["status_display_type"], StatusDisplayType.DETAILS)
                activity = Payload.set_activity(**arguments).data["args"]["activity"]
                self.assertEqual(activity["status_display_type"], 2)
                self.assertEqual(activity["details"], title or "Unknown game")
                self.assertEqual(activity["state"], "In multiplayer lobby")
                self.assertEqual(activity["timestamps"]["start"], 123)
                self.assertEqual(activity["assets"]["large_image"], "cover-key")
                self.assertEqual(activity["assets"]["large_text"], "PlayStation 3")

    def test_extracts_online_ps3_game(self) -> None:
        payload = {
            "profile": {
                "presences": [
                    {
                        "onlineStatus": "online",
                        "platform": "PS3",
                        "npTitleId": "BLUS12345_00",
                        "titleName": "Example PS3 Game",
                        "gameStatus": "Playing",
                        "npTitleIconUrl": "https://example.test/icon.png",
                    }
                ]
            }
        }

        presence = select_active_ps3_game(extract_legacy_presences(payload))

        self.assertIsNotNone(presence)
        assert presence is not None
        self.assertEqual(presence.platform, "PS3")
        self.assertEqual(presence.title_name, "Example PS3 Game")
        self.assertEqual(presence.title_icon_url, "https://example.test/icon.png")

    def test_supports_nested_title_info(self) -> None:
        payload = {
            "profile": {
                "presences": [
                    {
                        "onlineStatus": "online",
                        "platform": "PS3",
                        "titleInfo": {
                            "npTitleId": "NPEB12345_00",
                            "titleName": "Nested Example",
                        },
                    }
                ]
            }
        }

        presence = select_active_ps3_game(extract_legacy_presences(payload))

        self.assertIsNotNone(presence)
        assert presence is not None
        self.assertEqual(presence.title_name, "Nested Example")

    def test_ignores_offline_ps3_presence(self) -> None:
        payload = {
            "profile": {
                "presences": [
                    {
                        "onlineStatus": "offline",
                        "platform": "PS3",
                        "titleName": "Stale Game",
                    }
                ]
            }
        }

        self.assertIsNone(select_active_ps3_game(extract_legacy_presences(payload)))

    def test_generates_ps3_cover_from_title_id(self) -> None:
        class FakeTitle:
            def get_title_icon_url(self) -> str:
                return "https://example.test/generated-icon.png"

        class FakePsn:
            def game_title(self, **kwargs: object) -> FakeTitle:
                self.kwargs = kwargs
                return FakeTitle()

        game = LegacyPresence(
            online_status="online",
            platform="PS3",
            title_name="Example",
            title_id="BCES00001_00",
            game_status=None,
            title_icon_url=None,
        )

        resolver = Mock()
        resolver.resolve.side_effect = lambda _, source: square_cover_url(source)
        result = resolve_ps3_cover_url(FakePsn(), game, resolver=resolver)  # type: ignore[arg-type]

        self.assertIsNotNone(result)
        assert result is not None
        query = parse_qs(urlsplit(result).query)
        self.assertEqual(query["url"], ["https://example.test/generated-icon.png"])
        self.assertEqual(query["fit"], ["contain"])

    def test_square_cover_url_adds_transparent_padding(self) -> None:
        result = square_cover_url("https://example.test/wide cover.png")
        parsed = urlsplit(result)
        query = parse_qs(parsed.query)

        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}/", "https://wsrv.nl/")
        self.assertEqual(query["url"], ["https://example.test/wide cover.png"])
        self.assertEqual(query["w"], ["512"])
        self.assertEqual(query["h"], ["512"])
        self.assertEqual(query["fit"], ["contain"])
        self.assertEqual(query["cbg"], ["00000000"])
        self.assertEqual(query["output"], ["png"])


if __name__ == "__main__":
    unittest.main()
