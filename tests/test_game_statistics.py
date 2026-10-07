from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

from game_statistics import GameTimeTracker, format_playtime, _legacy_collection_start
from presence_parser import LegacyPresence
from time_format import format_russian_date


class Clock:
    value = 0.0
    def __call__(self):
        return self.value
    def wall(self):
        return 1_800_000_000 + self.value


GAME = LegacyPresence("online", "PS3", "inFamous", "BCES00609", None, "https://example.invalid/cover.png")
OTHER = replace(GAME, title_name="Journey", title_id="NPEA00288")


class GameStatisticsTests(unittest.TestCase):
    def tracker(self, path=None, **options):
        clock = Clock()
        return GameTimeTracker(path, clock=clock, wall_clock=clock.wall, **options), clock

    def advance(self, tracker, clock, seconds):
        for _ in range(seconds):
            clock.value += 1
            tracker.advance()

    def test_last_launch_uses_session_start_not_the_latest_poll_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "statistics.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            start = int(clock.wall())
            self.advance(tracker, clock, 8)
            tracker.observe(GAME, "Player")
            self.assertEqual(tracker.rows()[0]["lastPlayedAt"], start)
            tracker.observe(OTHER, "Player")
            self.advance(tracker, clock, 5)
            tracker.observe(GAME, "Player")
            second_start = int(clock.wall())
            self.advance(tracker, clock, 3)
            self.assertEqual(next(row for row in tracker.rows() if row["gameKey"] == GAME.title_id)["lastPlayedAt"], second_start)
            tracker.flush(force=True)
            reloaded = GameTimeTracker(path, clock=clock, wall_clock=clock.wall)
            row = next(row for row in reloaded.rows() if row["gameKey"] == GAME.title_id)
            self.assertEqual(row["lastPlayedAt"], second_start)
            self.assertEqual(row["lastPlayed"], format_russian_date(second_start, include_time=True))
            # Legacy rows without detailed history still have a usable date.
            reloaded._history.records.clear()
            row = next(row for row in reloaded.rows() if row["gameKey"] == GAME.title_id)
            self.assertEqual(row["lastPlayedAt"], int(clock.wall()))

    def test_same_game_and_status_changes_keep_one_session(self):
        tracker, clock = self.tracker()
        self.assertTrue(tracker.observe(GAME, "Player", started_at=int(clock.wall())-7))
        self.advance(tracker, clock, 5)
        self.assertFalse(tracker.observe(replace(GAME, game_status="New mission"), "PLAYER"))
        self.advance(tracker, clock, 4)
        self.assertEqual(tracker.rows()[0]["sessionCount"], 1)
        self.assertEqual(tracker.rows()[0]["playtime"], "00:00:09")
        self.assertEqual(tracker.session_elapsed, "00:00:16")

    def test_collection_date_starts_at_first_valid_game_and_remains_stable(self):
        tracker, clock = self.tracker()
        self.assertEqual(tracker.collection_started_date, "")
        tracker.observe(None, "Player")
        tracker.observe(GAME, None)
        self.assertEqual(tracker.collection_started_date, "")
        clock.value += 86400
        tracker.observe(GAME, "Player", started_at=int(clock.wall())-120)
        expected = format_russian_date(clock.wall())
        self.assertEqual(tracker.collection_started_date, expected)
        clock.value += 86400 * 2
        tracker.observe(OTHER, "Other account")
        self.assertEqual(tracker.collection_started_date, expected)

    def test_collection_date_persists_after_reload_and_later_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            expected = tracker.collection_started_date
            self.advance(tracker, clock, 5)
            tracker.close()
            reloaded, later = self.tracker(path)
            later.value += 86400 * 7
            reloaded.observe(OTHER, "Player")
            reloaded.close()
            final, _ = self.tracker(path)
            self.assertEqual(final.collection_started_date, expected)
            self.assertEqual(next(row for row in final.rows() if row["title"] == "inFamous")["totalSeconds"], 5)

    def test_legacy_date_recovery_preserves_totals_and_old_writer_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            first = int(clock.wall())
            self.advance(tracker, clock, 6)
            tracker.close()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("DROP TABLE statistics_metadata")  # Test-only old schema fixture.
            with patch("game_statistics._legacy_collection_start", return_value=first):
                migrated, later = self.tracker(path)
            self.assertEqual(migrated.collection_started_date, format_russian_date(first))
            self.assertEqual(migrated.rows()[0]["totalSeconds"], 6)
            later.value += 86400
            migrated.observe(GAME, "Player")
            migrated.close()
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT value FROM statistics_metadata").fetchone()[0], first)
                db.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?) ON CONFLICT(account,game_key) "
                    "DO UPDATE SET total_seconds=games.total_seconds+excluded.total_seconds",
                    ("player", GAME.title_id, GAME.title_name, "", 10, 0, int(later.wall())))
            final, _ = self.tracker(path)
            self.assertEqual(final.collection_started_date, migrated.collection_started_date)
            self.assertEqual(final.rows()[0]["totalSeconds"], 16)

    def test_legacy_date_uses_birth_time_not_metadata_change_time(self):
        path = Mock()
        path.stat.return_value = SimpleNamespace(st_birthtime=100, st_ctime=999)
        self.assertEqual(_legacy_collection_start(path, 200), 100)
        path.stat.return_value = SimpleNamespace(st_birthtime=300, st_ctime=999)
        self.assertEqual(_legacy_collection_start(path, 200), 200)
        path.stat.return_value = SimpleNamespace(st_ctime=999)
        self.assertEqual(_legacy_collection_start(path, 200), 200)

    def test_invalid_collection_date_is_rejected_without_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, _ = self.tracker(path)
            tracker.observe(GAME, "Player")
            tracker.close()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE statistics_metadata SET value='invalid'")
            with self.assertRaises(ValueError):
                self.tracker(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT value FROM statistics_metadata").fetchone()[0], "invalid")

    def test_switch_and_confirmed_idle_start_new_sessions(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 6)
        tracker.observe(OTHER, "Player")
        self.advance(tracker, clock, 4)
        tracker.observe(None, "Player", confirmed_idle=True)
        self.advance(tracker, clock, 10)
        tracker.observe(OTHER, "Player")
        rows = {row["title"]: row for row in tracker.rows()}
        self.assertEqual(rows["inFamous"]["totalSeconds"], 6)
        self.assertEqual(rows["Journey"]["totalSeconds"], 4)
        self.assertEqual(rows["Journey"]["sessionCount"], 2)
        self.assertEqual(tracker.session_elapsed, "00:00:00")

    def test_unknown_psn_gap_pauses_without_false_launch(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 6)
        tracker.observe(None, "Player")
        self.advance(tracker, clock, 20)
        self.assertTrue(tracker.rows()[0]["isPaused"])
        self.assertFalse(tracker.observe(GAME, "Player"))
        self.advance(tracker, clock, 4)
        self.assertEqual(tracker.rows()[0]["totalSeconds"], 10)
        self.assertEqual(tracker.rows()[0]["sessionCount"], 1)

    def test_sleep_gap_is_never_counted(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 5)
        clock.value += 3600
        tracker.advance()
        self.assertTrue(tracker.paused)
        self.advance(tracker, clock, 3)
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 2)
        self.assertEqual(tracker.rows()[0]["totalSeconds"], 7)

    def test_unconfirmed_stale_presence_stops_counting(self):
        tracker, clock = self.tracker(stale_after=30)
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 80)
        self.assertTrue(tracker.paused)
        self.assertEqual(tracker.rows()[0]["totalSeconds"], 30)

    def test_save_reload_never_backfills_time_while_app_was_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 12)
            tracker.close()
            reloaded, later = self.tracker(path)
            later.value = 86400
            self.assertEqual(reloaded.rows()[0]["totalSeconds"], 12)
            self.assertFalse(reloaded.rows()[0]["isCurrent"])
            reloaded.observe(GAME, "Player")
            self.advance(reloaded, later, 3)
            reloaded.close()
            final, _ = self.tracker(path)
            self.assertEqual(final.rows()[0]["totalSeconds"], 15)
            self.assertEqual(final.rows()[0]["sessionCount"], 2)
            self.assertEqual(final.rows()[0]["coverUrl"], GAME.title_icon_url)

    def test_failed_transaction_keeps_deltas_for_retry_without_double_counting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            self.advance(tracker, clock, 5)
            with patch("game_statistics.sqlite3.connect", side_effect=sqlite3.OperationalError("locked")):
                with self.assertRaises(sqlite3.OperationalError):
                    tracker.flush(force=True)
            tracker.flush(force=True)
            tracker.flush(force=True)
            reloaded, _ = self.tracker(path)
            self.assertEqual(reloaded.rows()[0]["totalSeconds"], 5)
            self.assertEqual(reloaded.rows()[0]["sessionCount"], 1)

    def test_accounts_are_separate_and_title_rename_keeps_same_game_key(self):
        tracker, clock = self.tracker()
        tracker.observe(GAME, "First")
        self.advance(tracker, clock, 5)
        tracker.observe(replace(GAME, title_name="inFamous RU"), "FIRST")
        self.assertEqual(len(tracker.rows()), 1)
        self.assertEqual(tracker.rows()[0]["sessionCount"], 1)
        tracker.observe(GAME, "Second")
        self.advance(tracker, clock, 3)
        self.assertEqual(tracker.rows()[0]["totalSeconds"], 3)
        tracker.observe(GAME, "First")
        self.assertEqual(tracker.rows()[0]["totalSeconds"], 5)

    def test_failed_save_throttles_retries_but_retains_pending_time(self):
        tracker, clock = self.tracker(Path("not-used.sqlite3"))
        tracker.observe(GAME, "Player")
        self.advance(tracker, clock, 15)
        with patch("game_statistics.sqlite3.connect", side_effect=sqlite3.OperationalError("locked")) as connect:
            with self.assertRaises(sqlite3.OperationalError):
                tracker.flush()
            clock.value += 1
            tracker.advance()
            self.assertFalse(tracker.flush())
            self.assertEqual(connect.call_count, 1)
            self.assertEqual(tracker._pending[("player", GAME.title_id)]["seconds"], 16)

    def test_invalid_saved_field_is_rejected_without_overwriting_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            tracker, clock = self.tracker(path)
            tracker.observe(GAME, "Player")
            tracker.close()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE games SET total_seconds='bad data'")
            with self.assertRaises(ValueError):
                self.tracker(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT total_seconds FROM games").fetchone()[0], "bad data")

    def test_two_writers_add_deltas_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            first, a = self.tracker(path)
            second, b = self.tracker(path)
            first.observe(GAME, "Player"); second.observe(GAME, "Player")
            self.advance(first, a, 3); self.advance(second, b, 5)
            first.close(); second.close()
            result, _ = self.tracker(path)
            self.assertEqual(result.rows()[0]["totalSeconds"], 8)
            self.assertEqual(result.rows()[0]["sessionCount"], 2)

    def test_invalid_database_is_preserved_and_not_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.sqlite3"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE user_data (value TEXT)")
                db.execute("INSERT INTO user_data VALUES ('keep')")
            with self.assertRaises(ValueError):
                self.tracker(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT value FROM user_data").fetchone()[0], "keep")

    def test_formatting_and_invalid_game_never_counts(self):
        self.assertEqual(format_playtime(-5), "00:00:00")
        self.assertEqual(format_playtime(360005.9), "100:00:05")
        tracker, clock = self.tracker()
        for game in (replace(GAME, online_status="offline"), replace(GAME, platform="PS5"), replace(GAME, title_name=None)):
            self.assertFalse(tracker.observe(game, "Player"))
            self.advance(tracker, clock, 2)
        self.assertEqual(tracker.rows(), [])
