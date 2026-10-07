"""Calendar-aware Russian/English date and duration formatting."""
from __future__ import annotations
import calendar
import time
from datetime import datetime


RUSSIAN_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
ENGLISH_MONTHS = ("January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December")


def format_russian_date(timestamp: float, *, include_time: bool = False,
                        include_seconds: bool = False, language: str = "ru") -> str:
    """Local date with explicit month names, independent of the Windows locale."""
    value = datetime.fromtimestamp(timestamp)
    months = ENGLISH_MONTHS if language == "en" else RUSSIAN_MONTHS
    result = f"{value.day} {months[value.month - 1]} {value.year}"
    if include_time or include_seconds:
        result += " · " + value.strftime("%H:%M:%S" if include_seconds else "%H:%M")
    return result


def format_playtime(seconds: float) -> str:
    hours, rest = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def russian_count(value: int, forms: tuple[str, str, str]) -> str:
    last_two = value % 100
    if 11 <= last_two <= 14:
        word = forms[2]
    else:
        word = forms[0 if value % 10 == 1 else 1 if 2 <= value % 10 <= 4 else 2]
    return f"{value} {word}"


def add_calendar_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def format_exact_remaining(expires_at: float, now: float | None = None, *, language: str = "ru") -> str:
    """Format calendar months, then days and clock units without approximation."""
    current = datetime.fromtimestamp(time.time() if now is None else now)
    expiry = datetime.fromtimestamp(expires_at)
    if expiry <= current:
        return "expired" if language == "en" else "истёк"
    months = (expiry.year - current.year) * 12 + expiry.month - current.month
    anchor = add_calendar_months(current, months)
    if anchor > expiry:
        months -= 1
        anchor = add_calendar_months(current, months)
    seconds = int((expiry - anchor).total_seconds())
    days, seconds = divmod(seconds, 86_400)
    hours, seconds = divmod(seconds, 3_600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if language == "en":
        units = ((months, "month"), (days, "day"), (hours, "hour"), (minutes, "minute"), (seconds, "second"))
        return ", ".join(f"{count} {unit}{'' if count == 1 else 's'}"
                         for count, unit in units if count or unit not in ("month", "day"))
    if months:
        parts.append(russian_count(months, ("месяц", "месяца", "месяцев")))
    if days:
        parts.append(russian_count(days, ("день", "дня", "дней")))
    parts.extend((
        russian_count(hours, ("час", "часа", "часов")),
        russian_count(minutes, ("минута", "минуты", "минут")),
        russian_count(seconds, ("секунда", "секунды", "секунд")),
    ))
    return ", ".join(parts)
