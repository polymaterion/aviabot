from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Subscription, SubscriptionStatus


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, subscription: Subscription) -> Subscription:
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: int, statuses: list[SubscriptionStatus] | None = None
    ) -> list[Subscription]:
        query = select(Subscription).where(Subscription.user_id == user_id)
        if statuses:
            query = query.where(Subscription.status.in_(statuses))
        query = query.order_by(Subscription.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_active(self) -> list[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def set_status(self, subscription: Subscription, status: SubscriptionStatus) -> None:
        subscription.status = status
        await self.session.flush()

    async def update_last_known_state(
        self,
        subscription: Subscription,
        *,
        price: float | None,
        flight_id: int | None,
        available: bool,
    ) -> None:
        from datetime import datetime, timezone

        subscription.last_known_price = price
        subscription.last_known_flight_id = flight_id
        subscription.last_seen_available = available
        subscription.last_checked_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def find_duplicate(
        self, user_id: int, search_key: str
    ) -> Subscription | None:
        """Защита от дублей подписок (п.45 ТЗ): один и тот же пользователь
        не должен иметь две активные подписки с одинаковым search_key."""
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.search_key == search_key,
                Subscription.status != SubscriptionStatus.DELETED,
            )
        )
        return result.scalar_one_or_none()
