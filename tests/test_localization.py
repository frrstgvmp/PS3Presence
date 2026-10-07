from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import settings_store
from localization import ENGLISH, normalize_language, translate
from time_format import format_exact_remaining, format_russian_date


class LocalizationTests(unittest.TestCase):
    def test_russian_default_and_language_persistence_preserve_other_settings(self):
        self.assertEqual(normalize_language(None), "ru")
        self.assertEqual(normalize_language("unknown"), "ru")
        with tempfile.TemporaryDirectory() as folder, patch.object(settings_store, "CONFIG_FILE", Path(folder)/"config.json"):
            settings_store.save_configuration(settings_store.StoredConfiguration("123", 45, "cover", {"2": (4, 8)}, "sakura"))
            self.assertEqual(settings_store.load_configuration().language, "ru")
            settings_store.save_language("en")
            settings_store.save_theme("terracotta")
            settings_store.save_light_offset(0, 2, 3)
            stored = settings_store.load_configuration()
            self.assertEqual(stored.language, "en")
            self.assertEqual((stored.discord_client_id, stored.poll_interval, stored.large_image), ("123", 45, "cover"))
            self.assertEqual(stored.light_offsets["2"], (4, 8))
            self.assertEqual(stored.theme_id, "terracotta")
            settings_store.save_language("ru")
            self.assertEqual(settings_store.load_configuration().language, "ru")

    def test_catalog_covers_all_qml_russian_strings(self):
        project = Path(__file__).resolve().parents[1]
        for file in (project/"qml").glob("*.qml"):
            for literal in re.findall(r'"(?:[^"\\]|\\.)*"', file.read_text(encoding="utf-8")):
                text = json.loads(literal)
                if re.search("[А-Яа-яЁё]", text):
                    if text == "Русский":  # Self-name of a language never changes.
                        continue
                    self.assertIn(text, ENGLISH, (file.name, text))
                    self.assertFalse(re.search("[А-Яа-яЁё]", translate(text, "en")), text)
                    self.assertEqual(translate(text, "ru"), text)

    def test_english_dates_durations_and_nested_error_prefixes(self):
        now = datetime(2026, 9, 13, 12).timestamp()
        expiry = datetime(2026, 10, 15, 15, 4, 5).timestamp()
        self.assertEqual(format_russian_date(now, language="en"), "13 September 2026")
        self.assertEqual(format_exact_remaining(expiry, now, language="en"), "1 month, 2 days, 3 hours, 4 minutes, 5 seconds")
        self.assertEqual(format_exact_remaining(now, now, language="en"), "expired")
        self.assertEqual(format_exact_remaining(now+1, now, language="en"), "0 hours, 0 minutes, 1 second")
        self.assertEqual(translate("Не удалось сохранить статистику: Некорректная дата статистики игры", "en"),
                         "Could not save statistics: Invalid game-statistics date")
