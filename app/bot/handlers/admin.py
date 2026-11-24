from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.texts import ru as t
from app.config.settings import get_settings
from app.database.models import User
from app.database.repositories.user_repository import UserRepository

router = Router(name="admin")

# Telegram ограничивает сообщение 4096 символами - при большом числе
# пользователей список бьётся на части такого размера.
_MAX_MESSAGE_LENGTH = 3500


def _display_name(user: User) -> str:
    """username, если есть, иначе имя, иначе просто 'без имени'."""
    if user.username:
        return f"@{user.username}"
    if user.first_name:
        return user.first_name
    return "без имени"


def _format_user_lines(users: list[User]) -> list[str]:
    return [
        t.USER_LINE.format(index=i, display_name=_display_name(u), telegram_id=u.telegram_id)
        for i, u in enumerate(users, start=1)
    ]


async def _send_in_chunks(message: Message, header: str, lines: list[str]) -> None:
    """Отправляет заголовок и список строк, разбивая на несколько
    сообщений, если суммарная длина превышает лимит Telegram."""
    await message.answer(header)

    if not lines:
        return

    chunk: list[str] = []
    chunk_length = 0
    for line in lines:
        if chunk_length + len(line) + 1 > _MAX_MESSAGE_LENGTH and chunk:
            await message.answer("\n".join(chunk))
            chunk = []
            chunk_length = 0
        chunk.append(line)
        chunk_length += len(line) + 1

    if chunk:
        await message.answer("\n".join(chunk))


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in get_settings().admin_telegram_ids


@router.message(Command("users"))
async def list_users(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t.ADMIN_ONLY)
        return

    users = await UserRepository(session).list_all()
    lines = _format_user_lines(users)
    await _send_in_chunks(message, t.USERS_LIST_HEADER.format(count=len(users)), lines)


@router.message(Command("new_users"))
async def list_new_users(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer(t.ADMIN_ONLY)
        return

    repo = UserRepository(session)
    new_users = await repo.list_unreported()

    if not new_users:
        await message.answer(t.NO_NEW_USERS)
        return

    lines = _format_user_lines(new_users)
    await _send_in_chunks(message, t.NEW_USERS_LIST_HEADER.format(count=len(new_users)), lines)

    # Помечаем как отправленных ТОЛЬКО после успешной отправки списка -
    # если бы это происходило до отправки и что-то сломалось, эти
    # пользователи потерялись бы из будущих /new_users навсегда.
    await repo.mark_reported(new_users)
