from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Airline:
    iata: str
    name: str
    flag: str


class AirlineService:
    """Справочник авиакомпаний (код IATA -> полное имя, флаг страны)
    для отображения в карточке билета. Данные вынесены в отдельный файл
    и не хранятся в коде, как и данные о городах."""

    def __init__(self, airlines_file: Path) -> None:
        self._airlines_file = airlines_file
        self._by_iata: dict[str, Airline] = {}
        self._load()

    def _load(self) -> None:
        with open(self._airlines_file, encoding="utf-8") as f:
            raw = json.load(f)
        self._by_iata = {
            item["iata"]: Airline(iata=item["iata"], name=item["name"], flag=item["flag"])
            for item in raw
        }

    def reload(self) -> None:
        self._load()

    def get(self, iata_or_name: str | None) -> Airline | None:
        if not iata_or_name:
            return None
        return self._by_iata.get(iata_or_name.upper())

    def display_name(self, iata_or_name: str | None) -> str:
        """Возвращает 'флаг Название' если код известен, иначе исходную
        строку (или заглушку, если её нет вовсе)."""
        if not iata_or_name:
            return "Авиакомпания уточняется"
        airline = self.get(iata_or_name)
        if airline is not None:
            return f"{airline.flag} {airline.name}"
        return iata_or_name
