from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        default_language: str = "ru",
        default_currency: str = "USD",
        username: str | None = None,
        first_name: str | None = None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            # Username/имя в Telegram могут поменяться - синхронизируем
            # при каждом визите, чтобы /users показывал актуальные данные.
            changed = False
            if username is not None and user.username != username:
                user.username = username
                changed = True
            if first_name is not None and user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if changed:
                await self.session.flush()
            return user

        user = User(
            telegram_id=telegram_id,
            language=default_language,
            currency=default_currency,
            username=username,
            first_name=first_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_language(self, user: User, language: str) -> None:
        user.language = language
        await self.session.flush()

    async def update_currency(self, user: User, currency: str) -> None:
        user.currency = currency
        await self.session.flush()

    async def toggle_notifications(self, user: User, enabled: bool) -> None:
        user.notifications_enabled = enabled
        await self.session.flush()

    async def list_all(self) -> list[User]:
        """Все зарегистрированные пользователи - для команды /users."""
        result = await self.session.execute(select(User).order_by(User.created_at))
        return list(result.scalars().all())

    async def list_unreported(self) -> list[User]:
        """Пользователи, ещё не выгруженные командой /new_users."""
        result = await self.session.execute(
            select(User).where(User.reported_as_new.is_(False)).order_by(User.created_at)
        )
        return list(result.scalars().all())

    async def mark_reported(self, users: list[User]) -> None:
        for user in users:
            user.reported_as_new = True
        await self.session.flush()
