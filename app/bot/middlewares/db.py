from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from app.database.repositories.user_repository import UserRepository
from app.database.session import get_session


class DatabaseMiddleware(BaseMiddleware):
    """Открывает сессию БД на каждое обновление и подгружает/создаёт
    пользователя (users.telegram_id), передавая их в data хендлера."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with get_session() as session:
            data["session"] = session

            tg_user: TgUser | None = data.get("event_from_user")
            if tg_user is not None:
                user_repo = UserRepository(session)
                user = await user_repo.get_or_create(
                    tg_user.id, username=tg_user.username, first_name=tg_user.first_name
                )
                data["user"] = user

            return await handler(event, data)
