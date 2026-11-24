from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

CB_PAGE_PREFIX = "page"  # {CB_PAGE_PREFIX}:{screen}:{index}


def pagination_row(*, screen: str, index: int, total: int) -> list[InlineKeyboardButton]:
    """Строка ◀️ N/M ▶️ для навигации между карточками одного экрана.
    screen различает контекст (flight_results / subscriptions), чтобы
    callback_data одного экрана не путался с другим."""
    if total <= 1:
        return []

    builder = InlineKeyboardBuilder()

    prev_index = (index - 1) % total
    next_index = (index + 1) % total

    builder.button(text="◀️", callback_data=f"{CB_PAGE_PREFIX}:{screen}:{prev_index}")
    builder.button(text=f"{index + 1}/{total}", callback_data="noop")
    builder.button(text="▶️", callback_data=f"{CB_PAGE_PREFIX}:{screen}:{next_index}")
    builder.adjust(3)

    rows = builder.export()
    return rows[0] if rows else []


def build_carousel_keyboard(
    *,
    screen: str,
    index: int,
    total: int,
    item_buttons: list[list[InlineKeyboardButton]],
    nav_first: bool = False,
) -> InlineKeyboardMarkup:
    """Собирает клавиатуру карусели.

    nav_first=True: строка навигации ◀️ N/M ▶️ идёт СРАЗУ под карточкой
    (первым рядом), затем кнопки конкретного элемента (купить/следить) -
    так пользователь сначала видит листание, потом действия с текущим
    элементом.
    nav_first=False (по умолчанию): кнопки элемента первыми, навигация
    снизу - используется там, где у элемента нет явного "основного"
    действия выше листания (например, карточка подписки).
    """
    builder = InlineKeyboardBuilder()
    nav_row = pagination_row(screen=screen, index=index, total=total)

    if nav_first and nav_row:
        builder.row(*nav_row)

    for row in item_buttons:
        builder.row(*row)

    if not nav_first and nav_row:
        builder.row(*nav_row)

    return builder.as_markup()
