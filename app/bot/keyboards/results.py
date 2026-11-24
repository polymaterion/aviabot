from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.carousel import build_carousel_keyboard
from app.bot.keyboards.main import CB_BACK_TO_MAIN_MENU, back_to_menu_button
from app.bot.texts import ru as t

CB_TRACK_PREFIX = "track"
SCREEN_FLIGHT_RESULTS = "flight_results"

CB_NO_RESULTS_CHANGE_DATES = "nores_change_dates"
CB_NO_RESULTS_INCREASE_BUDGET = "nores_increase_budget"
CB_NO_RESULTS_ALLOW_TRANSFERS = "nores_allow_transfers"
CB_NO_RESULTS_TRACK = "nores_track"

CB_OVER_BUDGET_TRACK = "overbudget_track"


def flight_card_keyboard(flight_index: int, total: int, booking_url: str) -> InlineKeyboardMarkup:
    """Карточка билета на карусельном фото-экране: строка листания ◀️ N/M ▶️
    сразу под карточкой, затем «Купить билет» (прямая URL-кнопка) и
    «Следить за ценой», и кнопка возврата в меню снизу - экран никогда не
    остаётся тупиком, даже долистав карусель до конца."""
    buy_button = InlineKeyboardButton(text=t.BTN_BUY_TICKET, url=booking_url)
    track_button = InlineKeyboardButton(
        text=t.BTN_TRACK_PRICE, callback_data=f"{CB_TRACK_PREFIX}:{flight_index}"
    )
    return build_carousel_keyboard(
        screen=SCREEN_FLIGHT_RESULTS,
        index=flight_index,
        total=total,
        item_buttons=[[buy_button], [track_button], [back_to_menu_button()]],
        nav_first=True,
    )


def no_results_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_CHANGE_DATES, callback_data=CB_NO_RESULTS_CHANGE_DATES)
    builder.button(text=t.BTN_INCREASE_BUDGET, callback_data=CB_NO_RESULTS_INCREASE_BUDGET)
    builder.button(text=t.BTN_ALLOW_TRANSFERS, callback_data=CB_NO_RESULTS_ALLOW_TRANSFERS)
    builder.button(text=t.BTN_TRACK_DIRECTION, callback_data=CB_NO_RESULTS_TRACK)
    builder.button(text=t.BTN_MAIN_MENU, callback_data=CB_BACK_TO_MAIN_MENU)
    builder.adjust(1)
    return builder.as_markup()


def over_budget_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_TRACK_PRICE, callback_data=CB_OVER_BUDGET_TRACK)
    builder.button(text=t.BTN_MAIN_MENU, callback_data=CB_BACK_TO_MAIN_MENU)
    builder.adjust(1)
    return builder.as_markup()
