from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from game_statistics import GameTimeTracker
from session_history import HISTORY_LIMIT, SessionHistory
from tests.test_game_statistics import Clock, GAME, OTHER
from time_format import format_russian_date


class SessionHistoryTests(unittest.TestCase):
    def tracker(self, path=None):
        clock = Clock()
        return GameTimeTracker(path, clock=clock, wall_clock=clock.wall), clock

    def advance(self, tracker, clock, seconds):
        for _ in range(seconds):
            clock.value += 1
            tracker.advance()

    def test_live_session_uses_observed_time_not_discord_base(self):
        tracker, clock = self.tracker()
        self.assertEqual(tracker.history_rows(), [])
        tracker.observe(GAME, "Player", started_at=int(clock.wall())-120)
        self.advance(tracker, clock, 5)
        row = tracker.history_rows()[0]
        self.assertEqual(row["playtime"], "00:00:05")
        self.assertEqual(tracker.session_elapsed, "00:02:05")
        self.assertEqual(row["startedAt"], format_russian_date(clock.wall()-5, include_seconds=True))
        self.assertEqual(row["endedAt"], "")
        self.assertTrue(row["isCurrent"])
        self.assertFalse(row["isPaused"])
        self.assertEqual(row["coverUrl"], GAME.title_icon_url)

    def test_status_change_cover_update_and_psn_pause_keep_same_session(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "Player")
        original_id = tracker.history_rows()[0]["sessionKey"]
        self.advance(tracker, clock, 5)
        tracker.observe(None, "Player")
        self.advance(tracker, clock, 20)
        self.assertTrue(tracker.history_rows()[0]["isPaused"])
        tracker.observe(replace(GAME, game_status="Mission", title_name="inFamous RU"), "PLAYER", "new-cover")
        self.advance(tracker, clock, 4)
        rows = tracker.history_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sessionKey"], original_id)
        self.assertEqual(rows[0]["totalSeconds"], 9)
        self.assertEqual(rows[0]["coverUrl"], "new-cover")
        self.assertEqual(rows[0]["title"], "inFamous RU")
        self.assertFalse(rows[0]["isPaused"])
        self.assertEqual(tracker.rows()[0]["totalSeconds"], rows[0]["totalSeconds"])

    def test_switch_idle_and_relaunch_create_distinct_ordered_records(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 6)
        tracker.observe(OTHER, "Player")
        self.advance(tracker, clock, 3)
        tracker.observe(None, "Player", confirmed_idle=True)
        tracker.observe(OTHER, "Player")  # Same wall second still has deterministic order.
        self.advance(tracker, clock, 2)
        rows = tracker.history_rows()
        self.assertEqual([row["title"] for row in rows], ["Journey", "Journey", "inFamous"])
        self.assertEqual([row["totalSeconds"] for row in rows], [2, 3, 6])
        self.assertEqual(len({row["sessionKey"] for row in rows}), 3)
        self.assertEqual(rows[1]["state"], "Сессия завершена")
        self.assertEqual(rows[2]["state"], "Смена игры")
        self.assertTrue(rows[1]["endedAt"])
        self.assertFalse(rows[1]["isCurrent"])

    def test_sleep_and_stale_presence_are_excluded_from_history_duration(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 5)
        clock.value += 3600
        tracker.advance()
        self.assertTrue(tracker.history_rows()[0]["isPaused"])
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 120)
        self.assertEqual(tracker.history_rows()[0]["totalSeconds"], 95)
        self.assertTrue(tracker.history_rows()[0]["isPaused"])

    def test_accounts_are_separate_and_account_change_closes_previous_session(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "First")
        self.advance(tracker, clock, 4)
        tracker.observe(OTHER, "Second")
        self.advance(tracker, clock, 2)
        self.assertEqual([row["title"] for row in tracker.history_rows()], ["Journey"])
        tracker.observe(GAME, "First")
        rows = tracker.history_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["state"], "Смена аккаунта")
        self.assertEqual(rows[1]["totalSeconds"], 4)

    def test_graceful_close_persists_end_and_reload_does_not_backfill(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 5)
            tracker.close()
            before = tracker.history_rows()[0]
            self.assertEqual(before["state"], "Программа закрыта")
            self.assertTrue(before["endedAt"])
            reloaded, later = self.tracker(path)
            later.value = 86400
            self.assertEqual(reloaded.history_rows()[0], before)
            reloaded.observe(GAME, "Player")
            self.advance(reloaded, later, 2)
            reloaded.close()
            final, _ = self.tracker(path)
            self.assertEqual(len(final.history_rows()), 2)
            self.assertEqual([row["totalSeconds"] for row in final.history_rows()], [2, 5])
            self.assertEqual(final.rows()[0]["totalSeconds"], 7)

    def test_crashed_checkpoint_is_interrupted_at_last_saved_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 15)
            tracker.flush(force=True)
            self.advance(tracker, clock, 3)  # Unsaved time is lost in simulated crash.
            reloaded, later = self.tracker(path)
            later.value = 86400
            row = reloaded.history_rows()[0]
            self.assertIn("Прервана", row["state"])
            self.assertFalse(row["isCurrent"])
            self.assertEqual(row["totalSeconds"], 15)
            self.assertEqual(row["endedAt"], format_russian_date(1_800_000_015, include_seconds=True))
            reloaded.flush(force=True)  # History-only recovery, no new aggregate delta.
            final, _ = self.tracker(path)
            self.assertEqual(final.history_rows()[0]["sessionKey"], row["sessionKey"])
            self.assertEqual(final.rows()[0]["totalSeconds"], 15)
            self.assertEqual(final.rows()[0]["sessionCount"], 1)

    def test_atomic_save_failure_retains_both_history_and_aggregate_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 5)
            tracker.observe(None, "Player", confirmed_idle=True)
            tracker.flush(force=True)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 3)
            with patch.object(SessionHistory, "write", side_effect=sqlite3.OperationalError("failed session write")):
                with self.assertRaises(sqlite3.OperationalError):
                    tracker.flush(force=True)
            saved, _ = self.tracker(path)
            self.assertEqual(saved.rows()[0]["totalSeconds"], 5)
            self.assertEqual(len(saved.history_rows()), 1)
            tracker.close()
            tracker.flush(force=True)
            final, _ = self.tracker(path)
            self.assertEqual(final.rows()[0]["totalSeconds"], 8)
            self.assertEqual(final.rows()[0]["sessionCount"], 2)
            self.assertEqual(sum(row["totalSeconds"] for row in final.history_rows()), 8)

    def test_legacy_aggregate_is_preserved_without_invented_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 10)
            tracker.close()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("DROP TABLE game_sessions")  # Test-only legacy fixture.
            reloaded, later = self.tracker(path)
            self.assertEqual(reloaded.rows()[0]["totalSeconds"], 10)
            self.assertEqual(reloaded.history_rows(), [])
            reloaded.observe(GAME, "Player")
            self.advance(reloaded, later, 2)
            reloaded.close()
            final, _ = self.tracker(path)
            self.assertEqual(final.rows()[0]["totalSeconds"], 12)
            self.assertEqual(len(final.history_rows()), 1)
            self.assertEqual(final.history_rows()[0]["totalSeconds"], 2)

    def test_display_is_bounded_but_database_keeps_all_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            for _ in range(HISTORY_LIMIT + 5):
                tracker.observe(GAME, "Player")
                tracker.observe(None, "Player", confirmed_idle=True)
            tracker.close()
            self.assertEqual(len(tracker.history_rows()), HISTORY_LIMIT)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM game_sessions").fetchone()[0], HISTORY_LIMIT + 5)
            reloaded, _ = self.tracker(path)
            self.assertEqual(len(reloaded.history_rows()), HISTORY_LIMIT)
            self.assertEqual([row["sessionKey"] for row in reloaded.history_rows()],
                             [row["sessionKey"] for row in tracker.history_rows()])

    def test_invalid_history_field_is_reported_without_overwriting_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, _ = self.tracker(path)
            tracker.observe(GAME, "Player")
            tracker.close()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE game_sessions SET started_at='bad date'")
            with self.assertRaises(ValueError):
                self.tracker(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT started_at FROM game_sessions").fetchone()[0], "bad date")
