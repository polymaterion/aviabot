from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "aviastan_logo.png"

# Telegram позволяet переиспользовать file_id уже загруженного файла вместо
# повторной загрузки - кэшируем его в памяти процесса после первой отправки.
_logo_file_id: str | None = None


def _logo_source():
    global _logo_file_id
    if _logo_file_id is not None:
        return _logo_file_id
    return FSInputFile(_LOGO_PATH)


async def _remember_file_id(message: Message) -> None:
    global _logo_file_id
    if _logo_file_id is None and message.photo:
        _logo_file_id = message.photo[-1].file_id


async def show_screen(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Показывает экран как НОВОЕ фото-сообщение, удаляя предыдущий экран,
    если он был. Используется после текстового ввода пользователя (дата,
    ручной город, цена) - ответ бота должен появиться в ленте ПОСЛЕ
    сообщения пользователя, а Telegram не позволяет переместить вниз уже
    существующее сообщение, поэтому старое удаляется и создаётся новое.
    """
    data = await state.get_data()
    old_message_id = data.get("screen_message_id")

    if old_message_id:
        try:
            await bot.delete_message(chat_id, old_message_id)
        except TelegramBadRequest:
            pass  # сообщение уже удалено/недоступно - не критично

    sent = await bot.send_photo(
        chat_id, photo=_logo_source(), caption=caption, reply_markup=reply_markup
    )
    await _remember_file_id(sent)
    await state.update_data(screen_message_id=sent.message_id)


async def update_screen(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Обновляет экран НА МЕСТЕ (edit) в ответ на нажатие inline-кнопки -
    то же сообщение, тот же файл, меняются только подпись и клавиатура.
    """
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        # Caption/markup не изменились - Telegram считает это ошибкой,
        # но для пользователя это не проблема (например, повторный тап).
        if "message is not modified" not in str(exc):
            raise
    await state.update_data(screen_message_id=callback.message.message_id)


async def notify_and_clear_screen(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Отправляет уведомление (например, о снижении цены) как обычное
    текстовое сообщение и удаляет текущий системный фото-экран (если он
    был открыт), чтобы в чате не оставалось старых меню поверх уведомления.

    В отличие от show_screen, само уведомление НЕ становится отслеживаемым
    screen_message_id - оно не должно быть удалено следующим действием
    бота (уведомления остаются в чате как история), и следующий системный
    экран не должен пытаться его удалить.
    """
    data = await state.get_data()
    old_message_id = data.get("screen_message_id")

    if old_message_id:
        try:
            await bot.delete_message(chat_id, old_message_id)
        except TelegramBadRequest:
            pass
        await state.update_data(screen_message_id=None)

    await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def clear_state_keep_screen(state: FSMContext) -> None:
    """Очищает FSM state (сбрасывает шаг/данные текущего флоу), но
    СОХРАНЯЕТ screen_message_id. Использовать перед show_screen/update_screen
    везде, где нужен полный сброс состояния (например, конец флоу
    поиска/редактирования) - иначе state.clear() стирает screen_message_id
    раньше, чем его успевают прочитать для удаления старого сообщения, и
    в чате остаётся висеть лишнее сообщение бота.
    """
    old_screen_id = (await state.get_data()).get("screen_message_id")
    await state.clear()
    await state.update_data(screen_message_id=old_screen_id)


async def start_screen(
    *,
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Первый показ экрана в разговоре (например, /start) - всегда новое
    сообщение, старого экрана ещё нет."""
    await state.update_data(screen_message_id=None)
    await show_screen(bot=bot, state=state, chat_id=chat_id, caption=caption, reply_markup=reply_markup)
