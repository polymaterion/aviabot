from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import ru as t

CB_MAIN_FIND_TICKET = "main_find_ticket"
CB_MAIN_MY_SUBSCRIPTIONS = "main_my_subscriptions"
CB_MAIN_SETTINGS = "main_settings"
CB_BACK_TO_MAIN_MENU = "back_to_main_menu"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню - inline-кнопки на фото-экране (единый UI на всём боте:
    одинаковая ширина карточки/кнопок на каждом экране)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_FIND_TICKET, callback_data=CB_MAIN_FIND_TICKET)
    builder.button(text=t.BTN_MY_SUBSCRIPTIONS, callback_data=CB_MAIN_MY_SUBSCRIPTIONS)
    builder.button(text=t.BTN_SETTINGS, callback_data=CB_MAIN_SETTINGS)
    builder.adjust(1, 2)
    return builder.as_markup()


def back_to_menu_button() -> InlineKeyboardButton:
    """Кнопка «⬅️ В главное меню» - используется на КАЖДОМ экране бота,
    у которого нет своего пути назад, чтобы ни один экран не был тупиком."""
    return InlineKeyboardButton(text=t.BTN_MAIN_MENU, callback_data=CB_BACK_TO_MAIN_MENU)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура из одной кнопки «В главное меню» - для экранов,
    где кроме выхода в меню больше ничего показывать не нужно (например,
    пустой список подписок)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_MAIN_MENU, callback_data=CB_BACK_TO_MAIN_MENU)
    return builder.as_markup()
