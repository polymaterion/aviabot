from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(slots=True, frozen=True)
class SearchParams:
    origin: str
    destination: str
    flexible: bool = False
    departure_date: Optional[date] = None
    departure_date_from: Optional[date] = None
    departure_date_to: Optional[date] = None
    return_date: Optional[date] = None
    return_date_from: Optional[date] = None
    return_date_to: Optional[date] = None
    direct_only: bool = False
    max_price: Optional[float] = None
    currency: str = "USD"


def build_search_key(params: SearchParams) -> str:
    """Строит нормализованный ключ параметров поиска (п.34, п.45 ТЗ).

    Используется:
    - как ключ кэша результатов поиска (учитывает все влияющие параметры);
    - для группировки одинаковых подписок разных пользователей (п.33 ТЗ),
      чтобы выполнить один API-запрос вместо N.

    max_price сознательно НЕ включается в ключ группировки API-запросов,
    т.к. он используется только для фильтрации уже полученных результатов
    на стороне бота, а не влияет на сам запрос к провайдеру.
    """
    payload = {
        "origin": params.origin.upper(),
        "destination": params.destination.upper(),
        "flexible": params.flexible,
        "departure_date": params.departure_date.isoformat() if params.departure_date else None,
        "departure_date_from": (
            params.departure_date_from.isoformat() if params.departure_date_from else None
        ),
        "departure_date_to": (
            params.departure_date_to.isoformat() if params.departure_date_to else None
        ),
        "return_date": params.return_date.isoformat() if params.return_date else None,
        "return_date_from": (
            params.return_date_from.isoformat() if params.return_date_from else None
        ),
        "return_date_to": params.return_date_to.isoformat() if params.return_date_to else None,
        "direct_only": params.direct_only,
        "currency": params.currency.upper(),
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
    return digest


def build_cache_key(params: SearchParams) -> str:
    """Ключ кэша включает дополнительно max_price, т.к. это отдельный
    поисковый сценарий с точки зрения пользователя (п.34 ТЗ)."""
    base = build_search_key(params)
    price_part = f"{params.max_price:.2f}" if params.max_price is not None else "none"
    return f"{base}:{price_part}"
