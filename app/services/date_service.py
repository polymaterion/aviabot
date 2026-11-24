from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


class DateParseError(Exception):
    """Не удалось распознать формат даты."""


class DateRangeOrderError(Exception):
    """Первая дата диапазона позже второй."""


class DateInPastError(Exception):
    """Дата находится в прошлом."""


@dataclass(slots=True, frozen=True)
class DateRange:
    start: date
    end: date


def _strip(text: str) -> str:
    return text.strip()


def parse_exact_date(raw: str, *, today: date | None = None) -> date:
    """Парсит дату в формате ДД.ММ.ГГ (п.13, п.48 ТЗ)."""
    today = today or date.today()
    cleaned = _strip(raw)
    try:
        parsed = datetime.strptime(cleaned, "%d.%m.%y").date()
    except ValueError as exc:
        raise DateParseError(str(exc)) from exc

    if parsed < today:
        raise DateInPastError(f"{parsed} is in the past")

    return parsed


def parse_date_range(raw: str, *, today: date | None = None) -> DateRange:
    """Парсит диапазон дат в формате ДД.ММ.ГГ-ДД.ММ.ГГ (п.14, п.48 ТЗ)."""
    today = today or date.today()
    cleaned = _strip(raw)

    parts = cleaned.split("-")
    if len(parts) != 2:
        raise DateParseError("expected format DD.MM.YY-DD.MM.YY")

    start_raw, end_raw = _strip(parts[0]), _strip(parts[1])

    try:
        start = datetime.strptime(start_raw, "%d.%m.%y").date()
        end = datetime.strptime(end_raw, "%d.%m.%y").date()
    except ValueError as exc:
        raise DateParseError(str(exc)) from exc

    if start < today:
        raise DateInPastError(f"{start} is in the past")

    if start > end:
        raise DateRangeOrderError(f"{start} is after {end}")

    return DateRange(start=start, end=end)


def validate_return_not_before_departure(
    departure: date, return_: date
) -> None:
    """Дата/диапазон возврата не может противоречить дате/диапазону вылета
    (п.16 ТЗ): возврат не раньше вылета."""
    if return_ < departure:
        raise DateRangeOrderError("return date is before departure date")


def format_date_ru(value: date) -> str:
    return value.strftime("%d.%m.%y")
