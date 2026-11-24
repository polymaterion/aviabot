from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.main import CB_BACK_TO_MAIN_MENU, main_menu_keyboard
from app.bot.screen.manager import clear_state_keep_screen, show_screen, update_screen
from app.bot.texts import ru as t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    # ВАЖНО: используем clear_state_keep_screen, а не state.clear() -
    # иначе screen_message_id стирается раньше, чем show_screen успевает
    # прочитать и удалить старое сообщение, и старый системный экран
    # остаётся висеть в чате.
    await clear_state_keep_screen(state)

    await show_screen(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        caption=t.WELCOME,
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == CB_BACK_TO_MAIN_MENU)
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Универсальный выход в главное меню - работает с ЛЮБОГО экрана бота
    (поиск, подписки, настройки), сбрасывая FSM-состояние. Гарантирует,
    что ни один экран не оказывается тупиком без пути назад."""
    await state.clear()
    await callback.answer()
    await update_screen(
        callback=callback, state=state, caption=t.MAIN_MENU, reply_markup=main_menu_keyboard()
    )
