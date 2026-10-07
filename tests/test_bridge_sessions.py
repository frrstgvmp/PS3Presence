from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from bridge import BridgePhase, BridgeSettings, PresenceBridge


class BridgeSessionTests(unittest.TestCase):
    def test_rpc_failure_status_change_and_reconnect_do_not_restart_game_clock(self):
        snapshots = []
        bridge = PresenceBridge(BridgeSettings("fake", "123", 30, None),
                                on_status=snapshots.append, on_log=lambda _: None)
        now = [1000]
        polls = [0]
        rpc = Mock()
        rpc.update.side_effect = [RuntimeError("unavailable"), None, None, None]
        client = Mock(online_id="Player")
        cover_cache = Mock()
        cover_cache.local_url.return_value = "file:///C:/test/cover.img"

        def payload(_):
            return {"profile": {"presences": [{"onlineStatus": "online", "platform": "PS3",
                "npTitleId": "BCES00609", "titleName": "inFamous", "gameStatus": str(polls[0])}]}}

        def wait(seconds):
            now[0] += seconds
            if seconds == 30:
                polls[0] += 1
                if polls[0] == 1:
                    bridge.request_reconnect()
                if polls[0] == 3:
                    bridge.stop()
            return bridge._stop_event.is_set()

        with ExitStack() as stack:
            stack.enter_context(patch("bridge.CoverResolver", return_value=cover_cache))
            stack.enter_context(patch("bridge.PSNAWP", return_value=Mock(me=Mock(return_value=client))))
            stack.enter_context(patch("bridge.get_legacy_profile_with_game_status", side_effect=payload))
            stack.enter_context(patch("bridge.refresh_token_expiration", return_value=None))
            stack.enter_context(patch("bridge.record_game_observation"))
            stack.enter_context(patch("bridge.resolve_ps3_cover_url", return_value="https://example.invalid/cover.png"))
            stack.enter_context(patch("bridge.connect_rpc_with_timeout"))
            stack.enter_context(patch("bridge.close_rpc_safely"))
            stack.enter_context(patch("pypresence.Presence", return_value=rpc))
            stack.enter_context(patch("bridge.time.time", side_effect=lambda: now[0]))
            stack.enter_context(patch.object(bridge, "_wait", side_effect=wait))
            bridge.run()

        self.assertEqual(rpc.update.call_count, 4)
        self.assertEqual({call.kwargs["start"] for call in rpc.update.call_args_list}, {1000})
        self.assertEqual({call.kwargs["large_image"] for call in rpc.update.call_args_list},
                         {"https://example.invalid/cover.png"})
        self.assertTrue(any(snapshot.local_cover_url == "file:///C:/test/cover.img" for snapshot in snapshots))
        self.assertEqual({snapshot.game_started_at for snapshot in snapshots if snapshot.game}, {1000})
        first_game = next(snapshot for snapshot in snapshots if snapshot.game)
        self.assertEqual(first_game.phase, BridgePhase.WATCHING)
        self.assertEqual(snapshots[-1].phase, BridgePhase.STOPPED)
