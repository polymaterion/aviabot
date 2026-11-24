from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.carousel import CB_PAGE_PREFIX
from app.bot.keyboards.main import back_to_menu_keyboard
from app.bot.keyboards.render import render_subscription_card
from app.bot.keyboards.subscriptions import (
    CB_SUB_DELETE,
    CB_SUB_EDIT,
    CB_SUB_EDIT_BACK,
    CB_SUB_EDIT_MAX_PRICE,
    CB_SUB_EDIT_REMOVE_MAX_PRICE,
    CB_SUB_EDIT_TOGGLE_DIRECT,
    SCREEN_SUBSCRIPTIONS,
    edit_subscription_keyboard,
    subscription_card_keyboard,
)
from app.bot.screen.manager import clear_state_keep_screen, show_screen, update_screen
from app.bot.states.search import EditSubscriptionState
from app.bot.texts import ru as t
from app.config.settings import get_settings
from app.database.models import User
from app.services.city_service import CityService
from app.services.subscription_service import SubscriptionService

router = Router(name="subscriptions")

settings = get_settings()
city_service = CityService(settings.cities_file)

# In-memory кэш списка подписок текущей карусели (аналогично _results_cache
# в search.py) - ключ chat_id, значение - список объектов Subscription для
# быстрого рендера страниц без повторных запросов к БД при листании.
_subscriptions_cache: dict[int, list] = {}


def _back_to_edit_menu_keyboard(index: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text=t.BTN_BACK, callback_data=f"{CB_SUB_EDIT_BACK}:{index}")
    return builder.as_markup()


async def _render_subscriptions_page(
    *, bot, state: FSMContext, chat_id: int, index: int, as_new_screen: bool, callback: CallbackQuery | None = None
) -> None:
    subscriptions = _subscriptions_cache.get(chat_id, [])
    if not subscriptions:
        return

    index = index % len(subscriptions)
    subscription = subscriptions[index]
    caption = render_subscription_card(subscription, city_service)
    keyboard = subscription_card_keyboard(subscription.id, index=index, total=len(subscriptions))

    if as_new_screen:
        await show_screen(bot=bot, state=state, chat_id=chat_id, caption=caption, reply_markup=keyboard)
    else:
        assert callback is not None
        await update_screen(callback=callback, state=state, caption=caption, reply_markup=keyboard)


@router.callback_query(F.data == "main_my_subscriptions")
async def list_subscriptions(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    service = SubscriptionService(session)
    subscriptions = await service.list_for_user(user.id)
    chat_id = callback.message.chat.id
    await callback.answer()

    if not subscriptions:
        _subscriptions_cache.pop(chat_id, None)
        await update_screen(
            callback=callback, state=state, caption=t.MY_SUBSCRIPTIONS_EMPTY, reply_markup=back_to_menu_keyboard()
        )
        return

    _subscriptions_cache[chat_id] = subscriptions
    await _render_subscriptions_page(
        bot=callback.bot,
        state=state,
        chat_id=chat_id,
        index=0,
        as_new_screen=False,
        callback=callback,
    )


@router.callback_query(F.data.startswith(f"{CB_PAGE_PREFIX}:{SCREEN_SUBSCRIPTIONS}:"))
async def paginate_subscriptions(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    await _render_subscriptions_page(
        bot=callback.bot,
        state=state,
        chat_id=callback.message.chat.id,
        index=index,
        as_new_screen=False,
        callback=callback,
    )


@router.callback_query(F.data.startswith(f"{CB_SUB_DELETE}:"))
async def delete_subscription(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    subscription_id = int(callback.data.split(":", 1)[1])
    service = SubscriptionService(session)
    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        await callback.answer(t.SUBSCRIPTION_NOT_FOUND, show_alert=True)
        return

    await service.delete(subscription)
    await callback.answer(t.SUBSCRIPTION_DELETED)

    chat_id = callback.message.chat.id
    subscriptions = [s for s in _subscriptions_cache.get(chat_id, []) if s.id != subscription_id]
    _subscriptions_cache[chat_id] = subscriptions

    if not subscriptions:
        await update_screen(
            callback=callback, state=state, caption=t.MY_SUBSCRIPTIONS_EMPTY, reply_markup=back_to_menu_keyboard()
        )
        return

    await _render_subscriptions_page(
        bot=callback.bot, state=state, chat_id=chat_id, index=0, as_new_screen=False, callback=callback
    )


@router.callback_query(F.data.startswith(f"{CB_SUB_EDIT}:"))
async def open_edit_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    subscription_id = int(callback.data.split(":", 1)[1])
    service = SubscriptionService(session)
    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        await callback.answer(t.SUBSCRIPTION_NOT_FOUND, show_alert=True)
        return

    subscriptions = _subscriptions_cache.get(callback.message.chat.id, [])
    index = next((i for i, s in enumerate(subscriptions) if s.id == subscription_id), 0)

    await callback.answer()
    await update_screen(
        callback=callback,
        state=state,
        caption=render_subscription_card(subscription, city_service),
        reply_markup=edit_subscription_keyboard(
            subscription.id,
            has_max_price=subscription.max_price is not None,
            direct_only=subscription.direct_only,
            index=index,
            total=len(subscriptions) or 1,
        ),
    )


@router.callback_query(F.data.startswith(f"{CB_SUB_EDIT_BACK}:"))
async def back_from_edit_menu(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await _render_subscriptions_page(
        bot=callback.bot,
        state=state,
        chat_id=callback.message.chat.id,
        index=index,
        as_new_screen=False,
        callback=callback,
    )


@router.callback_query(F.data.startswith(f"{CB_SUB_EDIT_MAX_PRICE}:"))
async def ask_new_max_price(callback: CallbackQuery, state: FSMContext) -> None:
    subscription_id = int(callback.data.split(":", 1)[1])
    subscriptions = _subscriptions_cache.get(callback.message.chat.id, [])
    index = next((i for i, s in enumerate(subscriptions) if s.id == subscription_id), 0)

    await state.update_data(editing_subscription_id=subscription_id, editing_index=index)
    await state.set_state(EditSubscriptionState.waiting_new_max_price)
    await callback.answer()

    # Кнопка «Назад» ведёт обратно в меню редактирования ЭТОЙ подписки,
    # а не в главное меню - иначе пользователь теряет контекст.
    await update_screen(
        callback=callback, state=state, caption=t.ASK_NEW_MAX_PRICE, reply_markup=_back_to_edit_menu_keyboard(index)
    )


@router.message(EditSubscriptionState.waiting_new_max_price)
async def new_max_price_entered(message, state: FSMContext, session: AsyncSession) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    data = await state.get_data()
    subscription_id = data.get("editing_subscription_id")
    editing_index = data.get("editing_index", 0)

    try:
        value = float(raw)
        if value <= 0:
            raise ValueError
    except ValueError:
        await show_screen(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            caption=t.MAX_PRICE_INVALID,
            reply_markup=_back_to_edit_menu_keyboard(editing_index),
        )
        return

    service = SubscriptionService(session)
    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        await clear_state_keep_screen(state)
        await show_screen(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            caption=t.SUBSCRIPTION_NOT_FOUND,
            reply_markup=back_to_menu_keyboard(),
        )
        return

    await service.update_max_price(subscription, value)
    await clear_state_keep_screen(state)

    subscriptions = _subscriptions_cache.get(message.chat.id, [])
    index = next((i for i, s in enumerate(subscriptions) if s.id == subscription_id), 0)

    await show_screen(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        caption=render_subscription_card(subscription, city_service),
        reply_markup=edit_subscription_keyboard(
            subscription.id,
            has_max_price=True,
            direct_only=subscription.direct_only,
            index=index,
            total=len(subscriptions) or 1,
        ),
    )


@router.callback_query(F.data.startswith(f"{CB_SUB_EDIT_REMOVE_MAX_PRICE}:"))
async def remove_max_price(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    subscription_id = int(callback.data.split(":", 1)[1])
    service = SubscriptionService(session)
    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        await callback.answer(t.SUBSCRIPTION_NOT_FOUND, show_alert=True)
        return

    await service.update_max_price(subscription, None)
    await callback.answer(t.SUBSCRIPTION_UPDATED)

    subscriptions = _subscriptions_cache.get(callback.message.chat.id, [])
    index = next((i for i, s in enumerate(subscriptions) if s.id == subscription_id), 0)

    await update_screen(
        callback=callback,
        state=state,
        caption=render_subscription_card(subscription, city_service),
        reply_markup=edit_subscription_keyboard(
            subscription.id,
            has_max_price=False,
            direct_only=subscription.direct_only,
            index=index,
            total=len(subscriptions) or 1,
        ),
    )


@router.callback_query(F.data.startswith(f"{CB_SUB_EDIT_TOGGLE_DIRECT}:"))
async def toggle_direct_only(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    subscription_id = int(callback.data.split(":", 1)[1])
    service = SubscriptionService(session)
    subscription = await service.get_by_id(subscription_id)
    if subscription is None:
        await callback.answer(t.SUBSCRIPTION_NOT_FOUND, show_alert=True)
        return

    await service.toggle_direct_only(subscription)
    await callback.answer(t.SUBSCRIPTION_UPDATED)

    subscriptions = _subscriptions_cache.get(callback.message.chat.id, [])
    index = next((i for i, s in enumerate(subscriptions) if s.id == subscription_id), 0)

    # Кнопка direct_only перерисовывается с АКТУАЛЬНЫМ состоянием после
    # toggle - subscription.direct_only уже обновлён сервисом.
    await update_screen(
        callback=callback,
        state=state,
        caption=render_subscription_card(subscription, city_service),
        reply_markup=edit_subscription_keyboard(
            subscription.id,
            has_max_price=subscription.max_price is not None,
            direct_only=subscription.direct_only,
            index=index,
            total=len(subscriptions) or 1,
        ),
    )
