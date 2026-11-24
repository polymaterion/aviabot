from __future__ import annotations

from datetime import datetime

from app.bot.texts import ru as t
from app.providers.base import FlightResult
from app.services.airline_service import AirlineService
from app.services.airport_service import AirportService
from app.services.city_service import CityService

_MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _format_day_month(dt: datetime) -> str:
    return f"{dt.day} {_MONTHS_RU[dt.month]}"


def _city_name(city_service: CityService, iata: str) -> str:
    city = city_service.get_by_iata(iata)
    return city.name if city is not None else iata


def render_flight_card(
    flight: FlightResult,
    city_service: CityService,
    airline_service: AirlineService,
    airport_service: AirportService,
) -> str:
    """Строит карточку билета в формате:

    🇦🇪 Flydubai

    Ашхабад — Москва (внуково)

    вылет 21 сентября в 05:15
    прилёт в 15:00

    🔁 С пересадкой (строка убирается, если рейс прямой)

    💰 46150 RUB

    Названия городов/аэропортов резолвятся через AirportService, который
    покрывает и групповые городские коды, и коды конкретных аэропортов
    (например, SHJ -> Шарджа, SVO -> Москва (шереметьево)), чтобы никакой
    код не оставался непереведённым в карточке.

    Travelpayouts (/aviasales/v3/prices_for_dates) не отдаёт город
    пересадки и время ожидания между рейсами - только число пересадок
    (transfers), поэтому карточка показывает «🔁 С пересадкой» одной
    строкой вместо выдуманной детализации, которой у провайдера нет.
    """
    airline_display = airline_service.display_name(flight.airline)

    # origin_airport/destination_airport - конкретный аэропорт (может
    # отличаться от общего городского кода) - используем его для
    # отображения, если он есть, иначе городской код origin/destination.
    origin_display = airport_service.display_name(flight.origin_airport or flight.origin)
    destination_display = airport_service.display_name(flight.destination_airport or flight.destination)

    departure_line = "-"
    if flight.departure_datetime:
        date_str = _format_day_month(flight.departure_datetime)
        time_str = flight.departure_datetime.strftime("%H:%M")
        departure_line = t.FLIGHT_CARD_DEPARTURE.format(date=date_str, time=time_str)

    arrival_line = "-"
    if flight.arrival_datetime:
        time_str = flight.arrival_datetime.strftime("%H:%M")
        arrival_line = t.FLIGHT_CARD_ARRIVAL.format(time=time_str)

    lines = [
        airline_display,
        "",
        f"{origin_display} ➜ {destination_display}",
        "",
        departure_line,
        arrival_line,
    ]

    if flight.direct is False:
        lines.append("")
        lines.append(t.FLIGHT_CARD_HAS_TRANSFERS)

    lines.append("")
    lines.append(t.FLIGHT_CARD_PRICE.format(price=f"{flight.price:.0f}", currency=flight.currency))

    return "\n".join(lines)


def render_subscription_card(subscription, city_service: CityService) -> str:
    """Строит карточку подписки для карусельного фото-экрана «Мои подписки»."""
    origin_name = _city_name(city_service, subscription.origin)
    destination_name = _city_name(city_service, subscription.destination)

    if subscription.flexible:
        date_str = (
            f"{_format_day_month(datetime.combine(subscription.departure_date_from, datetime.min.time()))}"
            f" - {_format_day_month(datetime.combine(subscription.departure_date_to, datetime.min.time()))}"
            if subscription.departure_date_from and subscription.departure_date_to
            else "гибкие даты"
        )
    else:
        date_str = (
            _format_day_month(datetime.combine(subscription.departure_date, datetime.min.time()))
            if subscription.departure_date
            else "-"
        )

    status_label = {
        "active": "🟢 Активна",
        "paused": "⏸ На паузе",
    }.get(subscription.status.value if hasattr(subscription.status, "value") else subscription.status, "")

    price = subscription.last_known_price
    price_line = (
        f"от {price:.0f} {subscription.currency}"
        if price is not None
        else "цена ещё не найдена"
    )

    max_price_line = (
        f"Бюджет: до {subscription.max_price:.0f} {subscription.currency}"
        if subscription.max_price is not None
        else "Бюджет: не ограничен"
    )
    direct_only_line = "Только прямые рейсы" if subscription.direct_only else "Прямые и с пересадкой"

    lines = [
        f"🔔 {origin_name} ➜ {destination_name}",
        "",
        date_str,
        price_line,
        "",
        max_price_line,
        direct_only_line,
        "",
        status_label,
    ]
    return "\n".join(lines)
