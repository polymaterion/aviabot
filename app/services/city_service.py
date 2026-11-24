from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class City:
    name: str
    country: str
    iata: str
    aliases: tuple[str, ...]
    category: str
    show_in_buttons: bool


class CityService:
    """Загружает и ищет города из единого файла data/cities.json (п.10, п.47 ТЗ).

    Список городов не хранится в коде. Каждый город размечен полем
    `category` (turkmenistan / turkmenistan_airlines_destination /
    popular_transit) и флагом `show_in_buttons` - показывать ли его кнопкой
    в быстром выборе на шагах "Откуда"/"Куда". Полный список (включая
    show_in_buttons=false) доступен через ручной ввод/поиск.
    """

    def __init__(self, cities_file: Path) -> None:
        self._cities_file = cities_file
        self._cities: list[City] = []
        self._by_iata: dict[str, City] = {}
        self._load()

    def _load(self) -> None:
        with open(self._cities_file, encoding="utf-8") as f:
            raw = json.load(f)
        self._cities = [
            City(
                name=c["name"],
                country=c["country"],
                iata=c["iata"],
                aliases=tuple(c.get("aliases", [])),
                category=c.get("category", "popular_transit"),
                show_in_buttons=bool(c.get("show_in_buttons", False)),
            )
            for c in raw
        ]
        self._by_iata = {c.iata: c for c in self._cities}

    def reload(self) -> None:
        self._load()

    def get_by_iata(self, iata: str) -> City | None:
        return self._by_iata.get(iata.upper())

    def get_quick_select(self, *, exclude_iata: str | None = None, count: int = 7) -> list[City]:
        """Возвращает плоский список городов для кнопок быстрого выбора
        (по умолчанию 7 штук - раскладка 3 ряда по 2 города + 1 ряд с
        одним городом и кнопкой "другой город").

        exclude_iata убирает конкретный город (например, уже выбранный
        как "Откуда") - вместо него в список подставляется следующий по
        порядку город из резервного пула (show_in_buttons=false), чтобы
        видимых кнопок всегда было ровно `count`, а не на одну меньше.
        """
        primary = [c for c in self._cities if c.show_in_buttons and c.iata != exclude_iata]

        if len(primary) >= count:
            return primary[:count]

        # Не хватает города (был исключён) - добираем из резерва: города,
        # которые обычно не показываются кнопками, в порядке появления в
        # cities.json, пропуская исключённый и уже отобранные.
        chosen_iatas = {c.iata for c in primary}
        reserve = [
            c
            for c in self._cities
            if not c.show_in_buttons and c.iata != exclude_iata and c.iata not in chosen_iatas
        ]

        result = list(primary)
        for city in reserve:
            if len(result) >= count:
                break
            result.append(city)

        return result

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower().replace("ё", "е")

    def search(self, query: str, *, exclude_iata: str | None = None, limit: int = 5) -> list[City]:
        """Пошаговый поиск (п.47 ТЗ):
        1. нормализация строки
        2. точное совпадение по имени/alias
        3. совпадение по alias (регистронезависимо)
        4. частичное совпадение (по началу слова, не по произвольной подстроке)

        exclude_iata исключает конкретный город из результатов (например,
        уже выбранный город отправления при вводе города назначения).
        """
        normalized_query = self._normalize(query)
        if not normalized_query:
            return []

        exact_matches: list[City] = []
        alias_matches: list[City] = []
        partial_matches: list[City] = []

        for city in self._cities:
            if city.iata == exclude_iata:
                continue

            normalized_name = self._normalize(city.name)
            normalized_aliases = [self._normalize(a) for a in city.aliases]
            normalized_iata = self._normalize(city.iata)

            if normalized_query == normalized_name or normalized_query == normalized_iata:
                exact_matches.append(city)
                continue
            if normalized_query in normalized_aliases:
                alias_matches.append(city)
                continue
            name_words = normalized_name.split()
            alias_words = [word for alias in normalized_aliases for word in alias.split()]
            all_words = [normalized_name, *normalized_aliases, *name_words, *alias_words]
            if any(word.startswith(normalized_query) for word in all_words):
                partial_matches.append(city)

        ordered = exact_matches + alias_matches + partial_matches
        seen: set[str] = set()
        result: list[City] = []
        for city in ordered:
            key = f"{city.iata}"
            if key in seen:
                continue
            seen.add(key)
            result.append(city)
            if len(result) >= limit:
                break
        return result
