from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Flight
from app.database.repositories.flight_repository import FlightRepository
from app.providers.base import FlightProvider, FlightResult
from app.providers.travelpayouts.client import TravelpayoutsAPIError
from app.services.search_cache import SearchCache
from app.services.search_key import SearchParams, build_cache_key

logger = logging.getLogger(__name__)


class FlightSearchError(Exception):
    """Окончательная ошибка поиска, показывается пользователю как общее
    сообщение без технического traceback (п.49 ТЗ)."""


class SearchService:
    """Оркестрирует поиск: кэш -> провайдер -> фильтрация -> сортировка ->
    дедупликация -> приведение к единому формату (п.25 ТЗ)."""

    def __init__(self, provider: FlightProvider, cache: SearchCache[list[FlightResult]]) -> None:
        self._provider = provider
        self._cache = cache

    async def search(self, params: SearchParams) -> list[FlightResult]:
        cache_key = build_cache_key(params)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("search_cache_hit", extra={"cache_key": cache_key})
            return cached

        try:
            results = await self._provider.search(
                origin=params.origin,
                destination=params.destination,
                departure_date=params.departure_date,
                departure_date_from=params.departure_date_from,
                departure_date_to=params.departure_date_to,
                return_date=params.return_date,
                return_date_from=params.return_date_from,
                return_date_to=params.return_date_to,
                flexible=params.flexible,
                currency=params.currency,
                direct_only=params.direct_only,
                max_price=params.max_price,
            )
        except TravelpayoutsAPIError as exc:
            logger.error("search_provider_error", extra={"error": str(exc)})
            raise FlightSearchError("provider unavailable") from exc

        deduped = self._deduplicate(results)
        self._cache.set(cache_key, deduped)
        return deduped

    @staticmethod
    def _deduplicate(results: list[FlightResult]) -> list[FlightResult]:
        seen: set[str] = set()
        deduped: list[FlightResult] = []
        for result in results:
            if result.external_id in seen:
                continue
            seen.add(result.external_id)
            deduped.append(result)
        return deduped

    @staticmethod
    def cheapest(results: list[FlightResult]) -> FlightResult | None:
        if not results:
            return None
        return min(results, key=lambda r: r.price)

    @staticmethod
    async def persist_results(
        session: AsyncSession, results: list[FlightResult]
    ) -> list[Flight]:
        """Сохраняет результаты поиска в БД (таблица flights) с защитой от
        дублей по (provider, external_id) - см. п.45 ТЗ."""
        repo = FlightRepository(session)
        persisted: list[Flight] = []
        for r in results:
            flight = Flight(
                provider=r.provider,
                external_id=r.external_id,
                airline=r.airline,
                flight_number=r.flight_number,
                origin=r.origin,
                destination=r.destination,
                departure_datetime=r.departure_datetime,
                arrival_datetime=r.arrival_datetime,
                return_departure_datetime=r.return_departure_datetime,
                return_arrival_datetime=r.return_arrival_datetime,
                price=r.price,
                currency=r.currency,
                direct=r.direct,
                duration=r.duration,
                baggage=r.baggage,
                booking_url=r.booking_url,
                parsed_at=r.parsed_at or datetime.now(timezone.utc),
            )
            persisted.append(await repo.upsert(flight))
        return persisted
