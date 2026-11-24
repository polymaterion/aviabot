from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from app.providers.base import FlightProvider, FlightResult
from app.providers.travelpayouts.client import TravelpayoutsAPIError, TravelpayoutsClient
from app.providers.travelpayouts.parser import (
    parse_prices_for_dates_response,
)

logger = logging.getLogger(__name__)


class TravelpayoutsProvider(FlightProvider):
    """Реализация FlightProvider поверх Travelpayouts Data API (п.22-23 ТЗ)."""

    name = "travelpayouts"

    def __init__(self, client: TravelpayoutsClient, affiliate_link_builder) -> None:
        self._client = client
        self._affiliate_link_builder = affiliate_link_builder

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
        try:
            if not flexible:
                results = await self._search_exact(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    currency=currency,
                    direct_only=direct_only,
                )
            else:
                results = await self._search_flexible(
                    origin=origin,
                    destination=destination,
                    departure_date_from=departure_date_from,
                    departure_date_to=departure_date_to,
                    currency=currency,
                    direct_only=direct_only,
                )
        except TravelpayoutsAPIError:
            logger.error(
                "travelpayouts_search_failed",
                extra={"origin": origin, "destination": destination},
            )
            raise

        if max_price is not None:
            results = [r for r in results if r.price <= max_price]

        results.sort(key=lambda r: (r.price, r.duration or 0, r.departure_datetime or date.min))
        return results

    async def _search_exact(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: Optional[date],
        return_date: Optional[date],
        currency: str,
        direct_only: bool,
    ) -> list[FlightResult]:
        payload = await self._client.search_prices_for_dates(
            origin=origin,
            destination=destination,
            departure_at=departure_date,
            return_at=return_date,
            currency=currency,
            direct=direct_only,
        )
        return parse_prices_for_dates_response(
            payload,
            origin=origin,
            destination=destination,
            currency=currency,
            affiliate_link_builder=self._affiliate_link_builder,
        )

    async def _search_flexible(
        self,
        *,
        origin: str,
        destination: str,
        departure_date_from: Optional[date],
        departure_date_to: Optional[date],
        currency: str,
        direct_only: bool,
    ) -> list[FlightResult]:
        """Для гибких дат выполняем поиск по точным датам в пределах диапазона
        и объединяем результаты. Диапазон ограничивается разумным числом
        запросов, чтобы не перегружать API."""
        if departure_date_from is None or departure_date_to is None:
            return []

        max_days_to_probe = 14
        span_days = (departure_date_to - departure_date_from).days + 1
        step = max(1, span_days // max_days_to_probe)

        all_results: list[FlightResult] = []
        current = departure_date_from
        probed = 0
        while current <= departure_date_to and probed < max_days_to_probe:
            payload = await self._client.search_prices_for_dates(
                origin=origin,
                destination=destination,
                departure_at=current,
                currency=currency,
                direct=direct_only,
            )
            all_results.extend(
                parse_prices_for_dates_response(
                    payload,
                    origin=origin,
                    destination=destination,
                    currency=currency,
                    affiliate_link_builder=self._affiliate_link_builder,
                )
            )
            current = current.fromordinal(current.toordinal() + step)
            probed += 1

        return all_results
