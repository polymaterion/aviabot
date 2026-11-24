from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.carousel import build_carousel_keyboard
from app.bot.keyboards.main import back_to_menu_button
from app.bot.texts import ru as t

SCREEN_SUBSCRIPTIONS = "subscriptions"

CB_SUB_DELETE = "sub_delete"
CB_SUB_EDIT = "sub_edit"
CB_SUB_EDIT_BACK = "sub_edit_back"

CB_SUB_EDIT_MAX_PRICE = "sub_edit_max_price"
CB_SUB_EDIT_TOGGLE_DIRECT = "sub_edit_toggle_direct"
CB_SUB_EDIT_REMOVE_MAX_PRICE = "sub_edit_remove_max_price"


def subscription_card_keyboard(subscription_id: int, *, index: int, total: int) -> InlineKeyboardMarkup:
    """Карточка подписки на карусельном фото-экране: строка навигации
    ◀️ N/M ▶️, кнопки управления (изменить/удалить) и кнопка возврата в
    меню - экран никогда не остаётся тупиком."""
    edit_button = InlineKeyboardButton(
        text=t.BTN_EDIT, callback_data=f"{CB_SUB_EDIT}:{subscription_id}"
    )
    delete_button = InlineKeyboardButton(
        text=t.BTN_DELETE, callback_data=f"{CB_SUB_DELETE}:{subscription_id}"
    )

    return build_carousel_keyboard(
        screen=SCREEN_SUBSCRIPTIONS,
        index=index,
        total=total,
        item_buttons=[[edit_button, delete_button], [back_to_menu_button()]],
    )


def edit_subscription_keyboard(
    subscription_id: int, has_max_price: bool, direct_only: bool, *, index: int, total: int
) -> InlineKeyboardMarkup:
    """Меню редактирования подписки - открывается на том же фото-экране.
    Кнопка «Назад» возвращает к карточке подписки (той же страницы карусели).
    Кнопка "прямые/с пересадкой" отражает ТЕКУЩЕЕ состояние подписки."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t.BTN_EDIT_MAX_PRICE, callback_data=f"{CB_SUB_EDIT_MAX_PRICE}:{subscription_id}"
    )
    if has_max_price:
        builder.button(
            text=t.BTN_EDIT_REMOVE_MAX_PRICE,
            callback_data=f"{CB_SUB_EDIT_REMOVE_MAX_PRICE}:{subscription_id}",
        )
    direct_label = t.BTN_DIRECT_ONLY_ON if direct_only else t.BTN_DIRECT_ONLY_OFF
    builder.button(
        text=direct_label, callback_data=f"{CB_SUB_EDIT_TOGGLE_DIRECT}:{subscription_id}"
    )
    builder.button(text=t.BTN_BACK, callback_data=f"{CB_SUB_EDIT_BACK}:{index}")
    builder.adjust(1)
    return builder.as_markup()
