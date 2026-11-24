from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Flight, FlightPriceHistory, Notification, Search


class FlightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_provider_external_id(
        self, provider: str, external_id: str
    ) -> Flight | None:
        result = await self.session.execute(
            select(Flight).where(
                Flight.provider == provider, Flight.external_id == external_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, flight: Flight) -> Flight:
        """Защита от дублей билетов (п.45 ТЗ): один и тот же билет от одного
        провайдера с одинаковым external_id не создаётся повторно."""
        existing = await self.get_by_provider_external_id(flight.provider, flight.external_id)
        if existing is None:
            self.session.add(flight)
            await self.session.flush()
            return flight

        existing.airline = flight.airline
        existing.flight_number = flight.flight_number
        existing.departure_datetime = flight.departure_datetime
        existing.arrival_datetime = flight.arrival_datetime
        existing.return_departure_datetime = flight.return_departure_datetime
        existing.return_arrival_datetime = flight.return_arrival_datetime
        existing.price = flight.price
        existing.currency = flight.currency
        existing.direct = flight.direct
        existing.duration = flight.duration
        existing.baggage = flight.baggage
        existing.booking_url = flight.booking_url
        existing.parsed_at = flight.parsed_at
        await self.session.flush()
        return existing

    async def get_by_id(self, flight_id: int) -> Flight | None:
        result = await self.session.execute(select(Flight).where(Flight.id == flight_id))
        return result.scalar_one_or_none()

    async def record_price_history(
        self,
        *,
        flight_id: int | None,
        subscription_id: int | None,
        price: float,
        currency: str,
    ) -> None:
        entry = FlightPriceHistory(
            flight_id=flight_id,
            subscription_id=subscription_id,
            price=price,
            currency=currency,
        )
        self.session.add(entry)
        await self.session.flush()

    async def add_notification(
        self,
        *,
        user_id: int,
        subscription_id: int | None,
        flight_id: int | None,
        type_: str,
        price: float | None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            subscription_id=subscription_id,
            flight_id=flight_id,
            type=type_,
            price=price,
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def add_search(
        self,
        *,
        user_id: int,
        origin: str,
        destination: str,
        departure_date,
        return_date,
        flexible: bool,
        filters: dict | None,
    ) -> Search:
        search = Search(
            user_id=user_id,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            flexible=flexible,
            filters=filters,
        )
        self.session.add(search)
        await self.session.flush()
        return search
