from __future__ import annotations

from datetime import date
from urllib.parse import urlencode


class AffiliateService:
    """Формирует партнёрские ссылки Travelpayouts (п.27 ТЗ).

    Отвечает за:
    - формирование партнёрской ссылки;
    - передачу параметров маршрута и дат;
    - добавление партнёрского маркера (marker).

    Бот не продаёт билеты сам - пользователь всегда переходит по этой
    ссылке на страницу продавца/сервиса бронирования.
    """

    def __init__(self, *, marker: str, base_url: str) -> None:
        self._marker = marker
        self._base_url = base_url.rstrip("/")

    def build_search_link(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: date | None = None,
        return_date: date | None = None,
    ) -> str:
        """Ссылка на страницу поиска у партнёра для маршрута/дат."""
        params = {
            "marker": self._marker,
            "origin_iata": origin,
            "destination_iata": destination,
        }
        if departure_date:
            params["depart_date"] = departure_date.isoformat()
        if return_date:
            params["return_date"] = return_date.isoformat()

        query = urlencode(params)
        return f"{self._base_url}/search?{query}"

    def build_booking_link(self, provider_link_path: str) -> str:
        """Дополняет booking-ссылку, полученную от Travelpayouts, партнёрским
        маркером, если он ещё не проставлен интеграцией."""
        if not provider_link_path:
            return self.build_search_link(origin="", destination="")

        separator = "&" if "?" in provider_link_path else "?"
        if "marker=" in provider_link_path:
            path = provider_link_path
        else:
            path = f"{provider_link_path}{separator}marker={self._marker}"

        if path.startswith("http"):
            return path
        return f"{self._base_url}{path if path.startswith('/') else '/' + path}"
