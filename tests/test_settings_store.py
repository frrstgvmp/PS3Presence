from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import settings_store


class SettingsStoreTests(unittest.TestCase):
    def test_light_offset_save_preserves_other_lamps_and_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings_store, "CONFIG_FILE", Path(directory) / "config.json"):
            settings_store.save_configuration(settings_store.StoredConfiguration("123", 45, "cover", {"0": (3, -4)}, "sakura"))
            settings_store.save_light_offset(18, 5, 14)
            settings_store.save_light_offset(1, -2, 7)
            loaded = settings_store.load_configuration()
            self.assertEqual(loaded.light_offsets, {"0": (3, -4), "18": (5, 14), "1": (-2, 7)})
            self.assertEqual((loaded.discord_client_id, loaded.poll_interval, loaded.large_image, loaded.theme_id),
                             ("123", 45, "cover", "sakura"))

    def test_aurora_is_default_without_overwriting_saved_theme(self) -> None:
        self.assertEqual(settings_store.StoredConfiguration().theme_id, "aurora")
        self.assertEqual(settings_store.normalize_theme_id(None), "aurora")
        self.assertEqual(settings_store.normalize_theme_id("unknown"), "aurora")
        with patch("settings_store.is_new_year_theme_available", return_value=False):
            self.assertEqual(settings_store.normalize_theme_id("newyear"), "aurora")
        with tempfile.TemporaryDirectory() as directory, patch.object(settings_store, "CONFIG_FILE", Path(directory) / "config.json"):
            self.assertEqual(settings_store.load_configuration().theme_id, "aurora")
            settings_store.save_configuration(settings_store.StoredConfiguration(theme_id="botanical"))
            self.assertEqual(settings_store.load_configuration().theme_id, "botanical")

    def test_new_year_theme_season_runs_from_december_10_through_january_20(self) -> None:
        self.assertFalse(settings_store.is_new_year_theme_available(date(2026, 12, 9)))
        self.assertTrue(settings_store.is_new_year_theme_available(date(2026, 12, 10)))
        self.assertTrue(settings_store.is_new_year_theme_available(date(2027, 1, 20)))
        self.assertFalse(settings_store.is_new_year_theme_available(date(2027, 1, 21)))

    def test_saves_configuration_and_encrypts_npsso_for_current_user(self) -> None:
        original_directory = settings_store.APP_DATA_DIR
        original_config = settings_store.CONFIG_FILE
        original_auth = settings_store.AUTH_FILE
        with tempfile.TemporaryDirectory() as directory:
            try:
                settings_store.APP_DATA_DIR = Path(directory)
                settings_store.CONFIG_FILE = Path(directory) / "config.json"
                settings_store.AUTH_FILE = Path(directory) / "auth.dat"
                settings_store.save_configuration(
                    settings_store.StoredConfiguration("1234567890", 45, "ps3")
                )
                try:
                    settings_store.save_npsso("local-test-secret")
                except OSError as error:
                    if error.errno == 2:
                        self.skipTest("The sandbox does not expose a loaded Windows user profile for DPAPI.")
                    raise
                self.assertEqual(settings_store.load_configuration().poll_interval, 45)
                self.assertEqual(settings_store.load_npsso(), "local-test-secret")
                self.assertNotIn(b"local-test-secret", settings_store.AUTH_FILE.read_bytes())
            finally:
                settings_store.APP_DATA_DIR = original_directory
                settings_store.CONFIG_FILE = original_config
                settings_store.AUTH_FILE = original_auth

    def test_theme_is_saved_without_losing_other_configuration(self) -> None:
        original_config = settings_store.CONFIG_FILE
        with tempfile.TemporaryDirectory() as directory:
            try:
                settings_store.CONFIG_FILE = Path(directory) / "config.json"
                settings_store.save_configuration(
                    settings_store.StoredConfiguration("1234567890", 45, "ps3", {"2": (4, -3)})
                )

                settings_store.save_theme("terracotta")

                loaded = settings_store.load_configuration()
                self.assertEqual(loaded.theme_id, "terracotta")
                self.assertEqual(loaded.discord_client_id, "1234567890")
                self.assertEqual(loaded.light_offsets, {"2": (4, -3)})
            finally:
                settings_store.CONFIG_FILE = original_config


if __name__ == "__main__":
    unittest.main()
