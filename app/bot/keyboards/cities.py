from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.texts import ru as t
from app.services.city_service import City

CB_CITY_PREFIX = "city"
CB_OTHER_CITY = "other_city"
CB_CANCEL_SEARCH = "cancel_search"


def _city_emoji(city: City) -> str:
    if city.category == "turkmenistan":
        return "🇹🇲"
    if city.category == "turkmenistan_airlines_destination":
        return "✈️"
    return "🌍"


def city_choice_keyboard(cities: list[City], *, step: str) -> InlineKeyboardMarkup:
    """step is 'origin' or 'destination', included in callback_data.

    Раскладка: 3 ряда по 2 города, 4-й ряд - один город и рядом кнопка
    «Другой город», 5-й ряд - «Отмена». Если городов меньше 7, «Другой
    город» просто встаёт в свой ряд один или с последним неполным рядом.
    """
    builder = InlineKeyboardBuilder()

    for city in cities:
        builder.button(
            text=f"{_city_emoji(city)} {city.name}", callback_data=f"{CB_CITY_PREFIX}:{step}:{city.iata}"
        )
    builder.button(text=t.BTN_OTHER_CITY, callback_data=f"{CB_OTHER_CITY}:{step}")
    builder.button(text=t.BTN_CANCEL, callback_data=CB_CANCEL_SEARCH)

    # 7 городов -> ряды по 2,2,2,1; "другой город" довешивается к 4-му
    # ряду (итого 2 кнопки в нём), "отмена" - отдельным рядом.
    full_pairs, remainder = divmod(len(cities), 2)
    row_sizes = [2] * full_pairs
    if remainder:
        row_sizes.append(remainder + 1)  # неполный ряд городов + "другой город" в этом же ряду
    else:
        row_sizes.append(1)  # ровное число городов - "другой город" в отдельном ряду
    row_sizes.append(1)  # "отмена"

    builder.adjust(*row_sizes)
    return builder.as_markup()


def city_variants_keyboard(cities: list[City], *, step: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.button(
            text=f"{city.name}, {city.country} ({city.iata})",
            callback_data=f"{CB_CITY_PREFIX}:{step}:{city.iata}",
        )
    builder.button(text=t.BTN_CANCEL, callback_data=CB_CANCEL_SEARCH)
    builder.adjust(1)
    return builder.as_markup()


def cancel_only_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура «только отмена» - для экранов, ожидающих текстовый ввод
    (дата, диапазон дат, ручной город, максимальная цена), которые иначе
    оставались бы полностью без кнопок и превращались в тупик."""
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_CANCEL, callback_data=CB_CANCEL_SEARCH)
    return builder.as_markup()
