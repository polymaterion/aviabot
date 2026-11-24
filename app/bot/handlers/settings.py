from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.settings import (
    CB_CURRENCY_PREFIX,
    CB_LANG_PREFIX,
    CB_SETTINGS_BACK,
    CB_SETTINGS_CURRENCY,
    CB_SETTINGS_LANGUAGE,
    CB_SETTINGS_NOTIFICATIONS_TOGGLE,
    currency_keyboard,
    language_keyboard,
    settings_menu_keyboard,
)
from app.bot.screen.manager import update_screen
from app.bot.texts import ru as t
from app.database.models import User
from app.database.repositories.user_repository import UserRepository

router = Router(name="settings")


@router.callback_query(F.data == "main_settings")
async def open_settings(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.answer()
    await update_screen(
        callback=callback,
        state=state,
        caption=t.SETTINGS_MENU,
        reply_markup=settings_menu_keyboard(user.notifications_enabled, user.currency),
    )


@router.callback_query(F.data == CB_SETTINGS_BACK)
async def back_to_settings(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    """Возврат из экрана выбора языка/валюты к меню настроек."""
    await callback.answer()
    await update_screen(
        callback=callback,
        state=state,
        caption=t.SETTINGS_MENU,
        reply_markup=settings_menu_keyboard(user.notifications_enabled, user.currency),
    )


@router.callback_query(F.data == CB_SETTINGS_LANGUAGE)
async def choose_language(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await update_screen(callback=callback, state=state, caption=t.CHOOSE_LANGUAGE, reply_markup=language_keyboard())


@router.callback_query(F.data == CB_SETTINGS_CURRENCY)
async def choose_currency(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await update_screen(callback=callback, state=state, caption=t.CHOOSE_CURRENCY, reply_markup=currency_keyboard())


@router.callback_query(F.data.startswith(f"{CB_LANG_PREFIX}:"))
async def set_language(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    code = callback.data.split(":", 1)[1]
    await UserRepository(session).update_language(user, code)
    await callback.answer(t.LANGUAGE_UPDATED)
    await update_screen(
        callback=callback,
        state=state,
        caption=t.SETTINGS_MENU,
        reply_markup=settings_menu_keyboard(user.notifications_enabled, user.currency),
    )


@router.callback_query(F.data.startswith(f"{CB_CURRENCY_PREFIX}:"))
async def set_currency(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    code = callback.data.split(":", 1)[1]
    await UserRepository(session).update_currency(user, code)
    await callback.answer(t.CURRENCY_UPDATED)
    await update_screen(
        callback=callback,
        state=state,
        caption=t.SETTINGS_MENU,
        reply_markup=settings_menu_keyboard(user.notifications_enabled, user.currency),
    )


@router.callback_query(F.data == CB_SETTINGS_NOTIFICATIONS_TOGGLE)
async def toggle_notifications(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    new_value = not user.notifications_enabled
    await UserRepository(session).toggle_notifications(user, new_value)
    await callback.answer()
    await update_screen(
        callback=callback,
        state=state,
        caption=t.SETTINGS_MENU,
        reply_markup=settings_menu_keyboard(user.notifications_enabled, user.currency),
    )
