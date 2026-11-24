from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.providers.base import FlightResult

PROVIDER_NAME = "travelpayouts"


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_prices_for_dates_item(
    item: dict[str, Any],
    *,
    origin: str,
    destination: str,
    currency: str,
    affiliate_link_builder,
) -> FlightResult:
    """Приводит один элемент ответа /aviasales/v3/prices_for_dates к
    единому внутреннему формату FlightResult (п.24 ТЗ).

    Реальные поля ответа (см. официальную документацию Aviasales Data API):
    origin, destination, origin_airport, destination_airport, price,
    airline, flight_number, departure_at, return_at, transfers,
    return_transfers, duration, duration_to, duration_back, link.

    Важно: эндпоинт НЕ отдаёт arrival_at вообще - только departure_at и
    длительность полёта в минутах. Время прибытия вычисляется как
    departure_at + duration_to (для перелёта туда) или + duration
    (если duration_to отсутствует, например для чистого one-way поиска,
    где API отдаёт duration как длительность самого перелёта).

    Эндпоинт также не предоставляет город/аэропорт пересадки и время
    ожидания между рейсами - только суммарное число пересадок (transfers),
    поэтому такие поля здесь не парсятся.
    """
    external_id = str(
        item.get("flight_number")
        or item.get("link")
        or f"{origin}-{destination}-{item.get('departure_at', '')}"
    )

    transfers = item.get("transfers")
    direct: Optional[bool] = None
    if transfers is not None:
        direct = transfers == 0

    # duration_to - длительность перелёта ТУДА в минутах (актуально и для
    # one-way, и для round-trip ответов). Если его нет - используем
    # duration как длительность одного перелёта (one-way без duration_to).
    duration_to_val = item.get("duration_to")
    duration_val = item.get("duration")
    duration = (
        int(duration_to_val)
        if isinstance(duration_to_val, (int, float))
        else int(duration_val) if isinstance(duration_val, (int, float)) else None
    )

    price_val = item.get("price")
    price = float(price_val) if price_val is not None else 0.0

    booking_path = item.get("link")
    booking_url = affiliate_link_builder(booking_path) if booking_path else None

    departure_dt = _parse_iso_datetime(item.get("departure_at"))
    arrival_dt = departure_dt + timedelta(minutes=duration) if departure_dt and duration else None

    return_departure_dt = _parse_iso_datetime(item.get("return_at"))
    duration_back_val = item.get("duration_back")
    duration_back = int(duration_back_val) if isinstance(duration_back_val, (int, float)) else None
    return_arrival_dt = (
        return_departure_dt + timedelta(minutes=duration_back)
        if return_departure_dt and duration_back
        else None
    )

    return FlightResult(
        external_id=external_id,
        provider=PROVIDER_NAME,
        airline=item.get("airline"),
        flight_number=str(item.get("flight_number")) if item.get("flight_number") is not None else None,
        origin=item.get("origin", origin),
        destination=item.get("destination", destination),
        origin_airport=item.get("origin_airport"),
        destination_airport=item.get("destination_airport"),
        departure_datetime=departure_dt,
        arrival_datetime=arrival_dt,
        return_departure_datetime=return_departure_dt,
        return_arrival_datetime=return_arrival_dt,
        price=price,
        currency=currency.upper(),
        direct=direct,
        duration=duration,
        baggage=None,  # Travelpayouts не предоставляет достоверную информацию о багаже в этом эндпоинте
        booking_url=booking_url,
        parsed_at=datetime.now(timezone.utc),
    )


def parse_prices_for_dates_response(
    payload: dict[str, Any],
    *,
    origin: str,
    destination: str,
    currency: str,
    affiliate_link_builder,
) -> list[FlightResult]:
    data = payload.get("data") or []
    return [
        parse_prices_for_dates_item(
            item,
            origin=origin,
            destination=destination,
            currency=currency,
            affiliate_link_builder=affiliate_link_builder,
        )
        for item in data
        if isinstance(item, dict)
    ]
