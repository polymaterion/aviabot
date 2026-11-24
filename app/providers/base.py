from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(slots=True)
class FlightResult:
    """Единая внутренняя модель авиабилета (п.24 ТЗ).

    Провайдер обязан приводить ответ API к этой структуре. Если поле
    отсутствует или недостоверно - используется None.

    Travelpayouts (/aviasales/v3/prices_for_dates) отдаёт маршрут одним
    отрезком origin -> destination с числом пересадок (transfers) и
    длительностью перелёта в минутах - без города пересадки, времени
    ожидания между рейсами или их отдельных номеров. Поэтому модель хранит
    маршрут одним отрезком, без сегментов маршрута.
    """

    external_id: str
    provider: str

    airline: Optional[str]
    flight_number: Optional[str]

    origin: str
    destination: str

    # IATA-код конкретного аэропорта (может отличаться от кода города,
    # например MOW -> DME/SVO/VKO) - используется, чтобы явно показать
    # смену аэропорта в карточке, если она есть.
    origin_airport: Optional[str] = None
    destination_airport: Optional[str] = None

    departure_datetime: Optional[datetime] = None
    arrival_datetime: Optional[datetime] = None
    return_departure_datetime: Optional[datetime] = None
    return_arrival_datetime: Optional[datetime] = None

    price: float = 0.0
    currency: str = "USD"

    direct: Optional[bool] = None
    duration: Optional[int] = None  # minutes
    baggage: Optional[str] = None

    booking_url: Optional[str] = None
    parsed_at: Optional[datetime] = None


class FlightProvider(ABC):
    """Единый интерфейс источника авиабилетов (п.23 ТЗ).

    Бизнес-логика бота зависит только от этого интерфейса, а не от
    конкретной структуры ответа Travelpayouts или любого другого API.
    Это позволяет в будущем добавить другие источники данных.
    """

    name: str

    @abstractmethod
    async def search(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: Optional[date] = None,
        departure_date_from: Optional[date] = None,
        departure_date_to: Optional[date] = None,
        return_date: Optional[date] = None,
        return_date_from: Optional[date] = None,
        return_date_to: Optional[date] = None,
        flexible: bool = False,
        currency: str = "USD",
        direct_only: bool = False,
        max_price: Optional[float] = None,
    ) -> list[FlightResult]:
        """Выполняет поиск и возвращает список результатов в едином формате."""
        raise NotImplementedError
