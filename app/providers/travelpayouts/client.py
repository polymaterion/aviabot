from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class TravelpayoutsAPIError(Exception):
    """Окончательная ошибка после исчерпания попыток запроса к Travelpayouts."""


class TravelpayoutsClient:
    """Тонкий HTTP-клиент к Travelpayouts Data API.

    Не содержит бизнес-логики бота - только запросы и повторные попытки.
    Точные эндпоинты и параметры должны сверяться с актуальной
    документацией Travelpayouts на момент разработки/эксплуатации.
    """

    def __init__(
        self,
        *,
        token: str,
        marker: str,
        base_url: str,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.5,
    ) -> None:
        self._token = token
        self._marker = marker
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {"X-Access-Token": self._token, "Accept-Encoding": "gzip"}

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                    last_error = exc
                    logger.warning(
                        "travelpayouts_request_failed",
                        extra={"attempt": attempt, "path": path, "error": str(exc)},
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._retry_backoff * attempt)

        logger.error("travelpayouts_request_exhausted", extra={"path": path})
        raise TravelpayoutsAPIError(str(last_error) if last_error else "unknown error")

    async def search_prices_for_dates(
        self,
        *,
        origin: str,
        destination: str,
        departure_at: Optional[date] = None,
        return_at: Optional[date] = None,
        currency: str = "usd",
        direct: bool = False,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Wraps GET /aviasales/v3/prices_for_dates (exact-date search).

        one_way определяется автоматически по наличию return_at:
        - есть return_at (ищем билет туда-обратно) -> one_way=false,
          иначе (по документации Travelpayouts) API вернёт только ОДИН
          билет вместо нескольких вариантов round-trip;
        - нет return_at (билет в одну сторону) -> one_way=true, чтобы
          результаты не группировались как половина round-trip маршрута.
        """
        one_way = return_at is None

        params: dict[str, Any] = {
            "origin": origin,
            "destination": destination,
            "currency": currency.lower(),
            "direct": str(direct).lower(),
            "one_way": str(one_way).lower(),
            "limit": limit,
            "sorting": "price",
            "token": self._token,
        }
        if departure_at:
            params["departure_at"] = departure_at.isoformat()
        if return_at:
            params["return_at"] = return_at.isoformat()
        return await self._request("/aviasales/v3/prices_for_dates", params)

    async def search_calendar_prices(
        self,
        *,
        origin: str,
        destination: str,
        month: date,
        currency: str = "usd",
    ) -> dict[str, Any]:
        """Wraps GET /v2/prices/month-matrix (flexible-date / calendar search)."""
        params: dict[str, Any] = {
            "origin": origin,
            "destination": destination,
            "month": month.replace(day=1).isoformat(),
            "currency": currency.lower(),
            "token": self._token,
        }
        return await self._request("/v2/prices/month-matrix", params)
