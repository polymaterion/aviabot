from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.main import back_to_menu_button
from app.bot.texts import ru as t

CB_SETTINGS_LANGUAGE = "settings_language"
CB_SETTINGS_CURRENCY = "settings_currency"
CB_SETTINGS_NOTIFICATIONS_TOGGLE = "settings_notif_toggle"
CB_SETTINGS_BACK = "settings_back"

CB_LANG_PREFIX = "lang"
CB_CURRENCY_PREFIX = "currency"

SUPPORTED_LANGUAGES = [("ru", "🇷🇺 Русский")]  # архитектура позволяет добавить tk/en позже
SUPPORTED_CURRENCIES = [("RUB", "🇷🇺 RUB"), ("USD", "🇺🇸 USD"), ("EUR", "🇪🇺 EUR")]


def settings_menu_keyboard(notifications_enabled: bool, currency: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_LANGUAGE, callback_data=CB_SETTINGS_LANGUAGE)
    builder.button(text=t.BTN_CURRENCY.format(currency=currency), callback_data=CB_SETTINGS_CURRENCY)

    status = t.NOTIFICATIONS_ENABLED if notifications_enabled else t.NOTIFICATIONS_DISABLED
    builder.button(
        text=t.NOTIFICATIONS_STATUS.format(status=status),
        callback_data=CB_SETTINGS_NOTIFICATIONS_TOGGLE,
    )
    builder.row(back_to_menu_button())
    builder.adjust(1)
    return builder.as_markup()


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in SUPPORTED_LANGUAGES:
        builder.button(text=label, callback_data=f"{CB_LANG_PREFIX}:{code}")
    builder.button(text=t.BTN_BACK, callback_data=CB_SETTINGS_BACK)
    builder.adjust(1)
    return builder.as_markup()


def currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in SUPPORTED_CURRENCIES:
        builder.button(text=label, callback_data=f"{CB_CURRENCY_PREFIX}:{code}")
    builder.row(InlineKeyboardButton(text=t.BTN_BACK, callback_data=CB_SETTINGS_BACK))
    builder.adjust(3, 1)
    return builder.as_markup()
