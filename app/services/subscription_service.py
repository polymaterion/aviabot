from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription, SubscriptionStatus
from app.database.repositories.subscription_repository import SubscriptionRepository
from app.services.search_key import SearchParams, build_search_key


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SubscriptionRepository(session)

    async def create_subscription(
        self,
        *,
        user_id: int,
        params: SearchParams,
        initial_price: float | None = None,
        initial_flight_id: int | None = None,
    ) -> Subscription:
        """Создаёт подписку (п.28 ТЗ), избегая дублей (п.45 ТЗ):
        если у пользователя уже есть активная/приостановленная подписка с
        тем же search_key, она возвращается вместо создания новой."""
        search_key = build_search_key(params)

        duplicate = await self._repo.find_duplicate(user_id, search_key)
        if duplicate is not None:
            if duplicate.status == SubscriptionStatus.PAUSED:
                await self._repo.set_status(duplicate, SubscriptionStatus.ACTIVE)
            return duplicate

        subscription = Subscription(
            user_id=user_id,
            origin=params.origin,
            destination=params.destination,
            flexible=params.flexible,
            departure_date=params.departure_date,
            departure_date_from=params.departure_date_from,
            departure_date_to=params.departure_date_to,
            return_date=params.return_date,
            return_date_from=params.return_date_from,
            return_date_to=params.return_date_to,
            max_price=params.max_price,
            direct_only=params.direct_only,
            currency=params.currency,
            status=SubscriptionStatus.ACTIVE,
            search_key=search_key,
            last_known_price=initial_price,
            last_known_flight_id=initial_flight_id,
            last_seen_available=initial_price is not None,
        )
        return await self._repo.create(subscription)

    async def list_for_user(self, user_id: int) -> list[Subscription]:
        return await self._repo.list_for_user(
            user_id, statuses=[SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED]
        )

    async def delete(self, subscription: Subscription) -> None:
        # Физическое удаление не выполняется - сохраняется для статистики
        # и истории (п.31 ТЗ), но исключается из мониторинга.
        await self._repo.set_status(subscription, SubscriptionStatus.DELETED)

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        return await self._repo.get_by_id(subscription_id)

    async def update_max_price(self, subscription: Subscription, max_price: float | None) -> None:
        """Изменяет максимальную цену существующей подписки (кнопка
        «✏️ Изменить», п.30 ТЗ) без создания новой записи."""
        subscription.max_price = max_price
        await self._session.flush()

    async def toggle_direct_only(self, subscription: Subscription) -> bool:
        subscription.direct_only = not subscription.direct_only
        await self._session.flush()
        return subscription.direct_only
