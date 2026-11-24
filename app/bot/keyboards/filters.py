from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import ru as t

CB_TOGGLE_DIRECT = "toggle_direct"
CB_SET_MAX_PRICE = "set_max_price"
CB_RUN_SEARCH = "run_search"
CB_CANCEL_SEARCH = "cancel_search"


def filters_keyboard(*, direct_only: bool, max_price: float | None) -> InlineKeyboardMarkup:
    """Пользователь либо настраивает фильтры (прямые рейсы / бюджет) и жмёт
    «Искать», либо сразу жмёт «Искать» без настройки - это и есть
    эквивалент «пропустить», поэтому отдельная кнопка «Пропустить» убрана
    как дублирующая «Искать» при пустых фильтрах."""
    builder = InlineKeyboardBuilder()

    direct_label = t.BTN_DIRECT_ONLY_ON if direct_only else t.BTN_DIRECT_ONLY_OFF
    builder.button(text=direct_label, callback_data=CB_TOGGLE_DIRECT)

    price_label = t.BTN_MAX_PRICE if max_price is None else f"{t.BTN_MAX_PRICE}: {int(max_price)}"
    builder.button(text=price_label, callback_data=CB_SET_MAX_PRICE)

    builder.button(text=t.BTN_SEARCH, callback_data=CB_RUN_SEARCH)
    builder.button(text=t.BTN_CANCEL, callback_data=CB_CANCEL_SEARCH)

    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()
