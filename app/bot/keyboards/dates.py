from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import ru as t

CB_DATE_EXACT = "date_exact"
CB_DATE_FLEXIBLE = "date_flexible"
CB_ROUND_TRIP_YES = "round_trip_yes"
CB_ROUND_TRIP_NO = "round_trip_no"
CB_CANCEL_SEARCH = "cancel_search"
CB_BACK = "back"


def date_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_EXACT_DATE, callback_data=CB_DATE_EXACT)
    builder.button(text=t.BTN_FLEXIBLE_DATES, callback_data=CB_DATE_FLEXIBLE)
    builder.button(text=t.BTN_CANCEL, callback_data=CB_CANCEL_SEARCH)
    builder.adjust(2, 1)
    return builder.as_markup()


def round_trip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_ROUND_TRIP_YES, callback_data=CB_ROUND_TRIP_YES)
    builder.button(text=t.BTN_ROUND_TRIP_NO, callback_data=CB_ROUND_TRIP_NO)
    builder.button(text=t.BTN_BACK, callback_data=CB_BACK)
    builder.adjust(1, 1, 1)
    return builder.as_markup()
