from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # Travelpayouts
    travelpayouts_token: str = Field(..., alias="TRAVELPOUTS_TOKEN")
    travelpayouts_marker: str = Field(..., alias="TRAVELPOUTS_MARKER")
    travelpayouts_base_url: str = Field(
        default="https://api.travelpayouts.com", alias="TRAVELPOUTS_BASE_URL"
    )
    travelpayouts_affiliate_base_url: str = Field(
        default="https://www.aviasales.com", alias="TRAVELPOUTS_AFFILIATE_BASE_URL"
    )

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # Monitoring / caching
    monitoring_interval_minutes: int = Field(default=15, alias="MONITORING_INTERVAL_MINUTES")
    search_cache_ttl: int = Field(default=900, alias="SEARCH_CACHE_TTL")
    search_history_limit: int = Field(default=20, alias="SEARCH_HISTORY_LIMIT")
    # Минимальное изменение цены, при котором отправляется уведомление о
    # снижении - задаётся ОТДЕЛЬНО для каждой валюты, потому что "300" в
    # рублях и "300" в долларах/евро означают совершенно разную величину
    # изменения. Формат: "RUB:300,USD:5,EUR:5" (валюта:порог через запятую).
    # Валюта, для которой порог не указан, использует price_drop_default_threshold.
    price_drop_thresholds_raw: str = Field(
        default="RUB:300,USD:5,EUR:5", alias="PRICE_DROP_NOTIFICATION_THRESHOLDS"
    )
    price_drop_default_threshold: float = Field(
        default=5.0, alias="PRICE_DROP_NOTIFICATION_DEFAULT_THRESHOLD"
    )

    @property
    def price_drop_thresholds(self) -> dict[str, float]:
        """Парсит price_drop_thresholds_raw в словарь {валюта: порог}."""
        result: dict[str, float] = {}
        for pair in self.price_drop_thresholds_raw.split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            currency, _, value = pair.partition(":")
            try:
                result[currency.strip().upper()] = float(value.strip())
            except ValueError:
                continue
        return result

    def price_drop_threshold_for(self, currency: str) -> float:
        """Возвращает порог уведомления о снижении цены для конкретной
        валюты, либо default, если для неё не задано отдельное значение."""
        return self.price_drop_thresholds.get(currency.upper(), self.price_drop_default_threshold)

    # HTTP client behaviour
    http_timeout_seconds: float = Field(default=15.0, alias="HTTP_TIMEOUT_SECONDS")
    http_max_retries: int = Field(default=3, alias="HTTP_MAX_RETRIES")
    http_retry_backoff_seconds: float = Field(default=1.5, alias="HTTP_RETRY_BACKOFF_SECONDS")

    # Misc
    default_language: str = Field(default="ru", alias="DEFAULT_LANGUAGE")
    default_currency: str = Field(default="USD", alias="DEFAULT_CURRENCY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Telegram ID пользователей, которым доступны админ-команды /users и
    # /new_users. Формат: список id через запятую, например "123456,789012".
    admin_telegram_ids_raw: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")

    @property
    def admin_telegram_ids(self) -> set[int]:
        result: set[int] = set()
        for part in self.admin_telegram_ids_raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                result.add(int(part))
            except ValueError:
                continue
        return result

    # Data files
    cities_file: Path = Field(default=BASE_DIR / "app" / "data" / "cities.json")
    airlines_file: Path = Field(default=BASE_DIR / "app" / "data" / "airlines.json")
    airports_file: Path = Field(default=BASE_DIR / "app" / "data" / "airports.json")
    texts_dir: Path = Field(default=BASE_DIR / "app" / "bot" / "texts")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
