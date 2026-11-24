from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class AirportEntry:
    iata: str
    city: str
    airport_note: str | None  # уточнение аэропорта в скобках, строчными буквами


class AirportService:
    """Резолвер названий по IATA-коду - покрывает и групповые городские
    коды (MOW для всей Москвы), и коды конкретных аэропортов (SVO, DME,
    VKO, SHJ и т.д.), чтобы ни один код, реально встречающийся в ответах
    Travelpayouts (origin/destination/origin_airport/destination_airport),
    не оставался непереведённым."""

    def __init__(self, airports_file: Path) -> None:
        self._airports_file = airports_file
        self._by_iata: dict[str, AirportEntry] = {}
        self._load()

    def _load(self) -> None:
        with open(self._airports_file, encoding="utf-8") as f:
            raw = json.load(f)
        self._by_iata = {
            item["iata"]: AirportEntry(
                iata=item["iata"], city=item["city"], airport_note=item.get("airport_note")
            )
            for item in raw
        }

    def reload(self) -> None:
        self._load()

    def get(self, iata: str) -> AirportEntry | None:
        return self._by_iata.get(iata.upper())

    def city_name(self, iata: str) -> str:
        """Название города по коду - работает как для городского кода
        (MOW), так и для кода конкретного аэропорта (SVO -> Москва).
        Если код неизвестен, возвращает сам код как крайний фоллбэк."""
        entry = self.get(iata)
        return entry.city if entry is not None else iata

    def display_name(self, iata: str) -> str:
        """Название для карточки билета: 'Москва' для городского кода,
        'Москва (внуково)' для кода конкретного аэропорта с уточнением."""
        entry = self.get(iata)
        if entry is None:
            return iata
        if entry.airport_note:
            return f"{entry.city} ({entry.airport_note})"
        return entry.city
