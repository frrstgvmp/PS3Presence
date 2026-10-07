from datetime import datetime
import unittest

from time_format import add_calendar_months, format_exact_remaining, russian_count, format_russian_date


class TimeFormatTests(unittest.TestCase):
    def test_all_month_names_and_date_clock_precision(self):
        names = ("января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря")
        for month, name in enumerate(names, 1):
            with self.subTest(month=month):
                timestamp = datetime(2026, month, 13, 20, 2, 27).timestamp()
                self.assertEqual(format_russian_date(timestamp), f"13 {name} 2026")
                self.assertEqual(format_russian_date(timestamp, include_time=True), f"13 {name} 2026 · 20:02")
                self.assertEqual(format_russian_date(timestamp, include_seconds=True), f"13 {name} 2026 · 20:02:27")

    def test_russian_numeral_forms(self):
        forms = ("день", "дня", "дней")
        for value, word in ((1, "день"), (2, "дня"), (5, "дней"), (11, "дней"),
                            (21, "день"), (22, "дня"), (111, "дней")):
            self.assertEqual(russian_count(value, forms), f"{value} {word}")

    def test_month_end_and_leap_year(self):
        self.assertEqual(add_calendar_months(datetime(2024, 1, 31), 1), datetime(2024, 2, 29))
        self.assertEqual(add_calendar_months(datetime(2025, 1, 31), 1), datetime(2025, 2, 28))
        self.assertEqual(add_calendar_months(datetime(2025, 12, 31), 1), datetime(2026, 1, 31))

    def test_exact_month_days_and_clock(self):
        now = datetime(2026, 9, 13, 12).timestamp()
        expiry = datetime(2026, 10, 15, 15, 4, 5).timestamp()
        self.assertEqual(format_exact_remaining(expiry, now),
                         "1 месяц, 2 дня, 3 часа, 4 минуты, 5 секунд")

    def test_partial_month_is_days_not_an_approximate_month(self):
        now = datetime(2026, 1, 31).timestamp()
        expiry = datetime(2026, 2, 27).timestamp()
        self.assertEqual(format_exact_remaining(expiry, now), "27 дней, 0 часов, 0 минут, 0 секунд")

    def test_expired_and_last_second(self):
        now = datetime(2026, 9, 13).timestamp()
        self.assertEqual(format_exact_remaining(now, now), "истёк")
        self.assertEqual(format_exact_remaining(now - 1, now), "истёк")
        self.assertEqual(format_exact_remaining(now + 1, now), "0 часов, 0 минут, 1 секунда")
