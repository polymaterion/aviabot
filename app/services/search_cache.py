from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class SearchCache(Generic[T]):
    """Простой in-memory TTL-кэш результатов поиска (п.34 ТЗ).

    Ключ кэша должен учитывать все параметры, влияющие на результат
    (это гарантируется тем, что вызывающий код строит ключ через
    search_key_service.build_search_key(...) перед обращением к кэшу).

    Для продакшена с несколькими инстансами бота этот кэш стоит заменить
    на Redis (см. п.53 ТЗ - Redis зарезервирован для будущего масштабирования).
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, _CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + self._ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)
