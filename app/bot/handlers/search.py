from __future__ import annotations

import logging
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.carousel import CB_PAGE_PREFIX
from app.bot.keyboards.cities import (
    CB_CANCEL_SEARCH,
    CB_CITY_PREFIX,
    CB_OTHER_CITY,
    cancel_only_keyboard,
    city_choice_keyboard,
    city_variants_keyboard,
)
from app.bot.keyboards.dates import (
    CB_BACK,
    CB_DATE_EXACT,
    CB_DATE_FLEXIBLE,
    CB_ROUND_TRIP_NO,
    CB_ROUND_TRIP_YES,
    date_type_keyboard,
    round_trip_keyboard,
)
from app.bot.keyboards.filters import (
    CB_RUN_SEARCH,
    CB_SET_MAX_PRICE,
    CB_TOGGLE_DIRECT,
    filters_keyboard,
)
from app.bot.keyboards.main import main_menu_keyboard
from app.bot.keyboards.render import render_flight_card
from app.bot.keyboards.results import (
    CB_NO_RESULTS_ALLOW_TRANSFERS,
    CB_NO_RESULTS_CHANGE_DATES,
    CB_NO_RESULTS_INCREASE_BUDGET,
    CB_NO_RESULTS_TRACK,
    CB_OVER_BUDGET_TRACK,
    CB_TRACK_PREFIX,
    SCREEN_FLIGHT_RESULTS,
    flight_card_keyboard,
    no_results_keyboard,
    over_budget_keyboard,
)
from app.bot.screen.manager import show_screen, update_screen
from app.bot.states.search import SearchState
from app.bot.texts import ru as t
from app.config.settings import get_settings
from app.database.models import User
from app.database.repositories.flight_repository import FlightRepository
from app.providers.travelpayouts.client import TravelpayoutsClient
from app.providers.travelpayouts.provider import TravelpayoutsProvider
from app.services.affiliate_service import AffiliateService
from app.services.airline_service import AirlineService
from app.services.airport_service import AirportService
from app.services.city_service import CityService
from app.services.date_service import (
    DateInPastError,
    DateParseError,
    DateRangeOrderError,
    format_date_ru,
    parse_date_range,
    parse_exact_date,
    validate_return_not_before_departure,
)
from app.services.search_cache import SearchCache
from app.services.search_key import SearchParams
from app.services.search_service import FlightSearchError, SearchService
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)
router = Router(name="search")

settings = get_settings()
city_service = CityService(settings.cities_file)
airline_service = AirlineService(settings.airlines_file)
airport_service = AirportService(settings.airports_file)
affiliate_service = AffiliateService(
    marker=settings.travelpayouts_marker, base_url=settings.travelpayouts_affiliate_base_url
)
_travelpayouts_client = TravelpayoutsClient(
    token=settings.travelpayouts_token,
    marker=settings.travelpayouts_marker,
    base_url=settings.travelpayouts_base_url,
    timeout_seconds=settings.http_timeout_seconds,
    max_retries=settings.http_max_retries,
    retry_backoff_seconds=settings.http_retry_backoff_seconds,
)
_provider = TravelpayoutsProvider(_travelpayouts_client, affiliate_service.build_booking_link)
_search_cache: SearchCache = SearchCache(ttl_seconds=settings.search_cache_ttl)
search_service = SearchService(_provider, _search_cache)

# In-memory хранилище результатов поиска текущей сессии просмотра
# результатов (п.61 ТЗ). Ключ - telegram chat_id. Хранит объекты
# FlightResult целиком, чтобы карточка каждой карусельной страницы
# рендерилась без похода в БД.
_results_cache: dict[int, list] = {}


def _default_booking_link(origin: str, destination: str) -> str:
    return affiliate_service.build_search_link(origin=origin, destination=destination)


# --- Entry point ---


@router.callback_query(F.data == "main_find_ticket")
async def start_search(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await state.clear()
    _results_cache.pop(callback.message.chat.id, None)
    quick_cities = city_service.get_quick_select()
    await state.set_state(SearchState.waiting_origin)
    # Валюта пользователя (настраивается в ⚙️ Настройки) фиксируется в
    # начале поиска и используется во всех запросах к провайдеру и при
    # отображении цен - раньше здесь ошибочно был жёстко закодирован USD.
    await state.update_data(currency=user.currency)
    await callback.answer()
    await update_screen(
        callback=callback,
        state=state,
        caption=t.ASK_ORIGIN,
        reply_markup=city_choice_keyboard(quick_cities, step="origin"),
    )


@router.callback_query(F.data == CB_CANCEL_SEARCH)
async def cancel_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer(t.SEARCH_CANCELLED)
    await update_screen(
        callback=callback, state=state, caption=t.MAIN_MENU, reply_markup=main_menu_keyboard()
    )


# --- Origin / destination selection ---


@router.callback_query(F.data.startswith(f"{CB_CITY_PREFIX}:"))
async def city_selected(callback: CallbackQuery, state: FSMContext) -> None:
    _, step, iata = callback.data.split(":")
    city = city_service.get_by_iata(iata)
    await callback.answer()

    if city is None:
        await update_screen(callback=callback, state=state, caption=t.CITY_NOT_FOUND, reply_markup=cancel_only_keyboard())
        return

    if step == "origin":
        await state.update_data(origin=city.iata, origin_name=city.name)
        quick_cities = city_service.get_quick_select(exclude_iata=city.iata)
        await state.set_state(SearchState.waiting_destination)
        await update_screen(
            callback=callback,
            state=state,
            caption=t.ASK_DESTINATION,
            reply_markup=city_choice_keyboard(quick_cities, step="destination"),
        )
    else:
        await state.update_data(destination=city.iata, destination_name=city.name)
        await state.set_state(SearchState.waiting_date_type)
        await update_screen(
            callback=callback, state=state, caption=t.ASK_DATE_TYPE, reply_markup=date_type_keyboard()
        )


@router.callback_query(F.data.startswith(f"{CB_OTHER_CITY}:"))
async def other_city_requested(callback: CallbackQuery, state: FSMContext) -> None:
    _, step = callback.data.split(":")
    await callback.answer()
    target_state = (
        SearchState.waiting_origin_manual if step == "origin" else SearchState.waiting_destination_manual
    )
    await state.update_data(city_step=step)
    await state.set_state(target_state)
    await update_screen(callback=callback, state=state, caption=t.ASK_CITY_MANUAL, reply_markup=cancel_only_keyboard())


@router.message(SearchState.waiting_origin_manual)
@router.message(SearchState.waiting_destination_manual)
async def manual_city_input(message, state: FSMContext) -> None:
    data = await state.get_data()
    step = data.get("city_step", "origin")
    exclude_iata = data.get("origin") if step == "destination" else None

    matches = city_service.search(message.text or "", exclude_iata=exclude_iata)
    if not matches:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.CITY_NOT_FOUND, reply_markup=cancel_only_keyboard())
        return

    if len(matches) == 1:
        await _apply_city_choice(message, state, step, matches[0].iata)
        return

    await state.set_state(
        SearchState.waiting_origin_choice if step == "origin" else SearchState.waiting_destination_choice
    )
    await show_screen(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        caption=t.CITY_CHOOSE_VARIANT,
        reply_markup=city_variants_keyboard(matches, step=step),
    )


async def _apply_city_choice(message, state: FSMContext, step: str, iata: str) -> None:
    city = city_service.get_by_iata(iata)
    if city is None:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.CITY_NOT_FOUND, reply_markup=cancel_only_keyboard())
        return

    if step == "origin":
        await state.update_data(origin=city.iata, origin_name=city.name)
        quick_cities = city_service.get_quick_select(exclude_iata=city.iata)
        await state.set_state(SearchState.waiting_destination)
        await show_screen(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            caption=t.ASK_DESTINATION,
            reply_markup=city_choice_keyboard(quick_cities, step="destination"),
        )
    else:
        await state.update_data(destination=city.iata, destination_name=city.name)
        await state.set_state(SearchState.waiting_date_type)
        await show_screen(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            caption=t.ASK_DATE_TYPE,
            reply_markup=date_type_keyboard(),
        )


# --- Date type ---


@router.callback_query(F.data == CB_DATE_EXACT)
async def choose_exact_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(flexible=False)
    await state.set_state(SearchState.waiting_departure_date)
    await callback.answer()
    await update_screen(callback=callback, state=state, caption=t.ASK_EXACT_DEPARTURE_DATE, reply_markup=cancel_only_keyboard())


@router.callback_query(F.data == CB_DATE_FLEXIBLE)
async def choose_flexible_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(flexible=True)
    await state.set_state(SearchState.waiting_departure_range)
    await callback.answer()
    await update_screen(callback=callback, state=state, caption=t.ASK_FLEXIBLE_DEPARTURE_RANGE, reply_markup=cancel_only_keyboard())


@router.message(SearchState.waiting_departure_date)
async def departure_date_entered(message, state: FSMContext) -> None:
    try:
        parsed = parse_exact_date(message.text or "")
    except DateInPastError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_IN_PAST_ERROR, reply_markup=cancel_only_keyboard())
        return
    except DateParseError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_PARSE_ERROR, reply_markup=cancel_only_keyboard())
        return

    await state.update_data(departure_date=parsed.isoformat())
    await state.set_state(SearchState.waiting_round_trip)
    await show_screen(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        caption=t.ASK_ROUND_TRIP,
        reply_markup=round_trip_keyboard(),
    )


@router.message(SearchState.waiting_departure_range)
async def departure_range_entered(message, state: FSMContext) -> None:
    try:
        date_range = parse_date_range(message.text or "")
    except DateInPastError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_IN_PAST_ERROR, reply_markup=cancel_only_keyboard())
        return
    except DateRangeOrderError:
        await show_screen(
            bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_RANGE_INVALID_ORDER_ERROR, reply_markup=cancel_only_keyboard()
        )
        return
    except DateParseError:
        await show_screen(
            bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_RANGE_PARSE_ERROR, reply_markup=cancel_only_keyboard()
        )
        return

    await state.update_data(
        departure_date_from=date_range.start.isoformat(),
        departure_date_to=date_range.end.isoformat(),
    )
    await state.set_state(SearchState.waiting_round_trip)
    await show_screen(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        caption=t.ASK_ROUND_TRIP,
        reply_markup=round_trip_keyboard(),
    )


# --- Round trip ---


@router.callback_query(F.data == CB_ROUND_TRIP_NO)
async def round_trip_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(round_trip=False)
    await callback.answer()
    await _show_filters(callback, state)


@router.callback_query(F.data == CB_ROUND_TRIP_YES)
async def round_trip_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(round_trip=True)
    data = await state.get_data()
    await callback.answer()
    if data.get("flexible"):
        await state.set_state(SearchState.waiting_return_range)
        await update_screen(callback=callback, state=state, caption=t.ASK_FLEXIBLE_RETURN_RANGE, reply_markup=cancel_only_keyboard())
    else:
        await state.set_state(SearchState.waiting_return_date)
        await update_screen(callback=callback, state=state, caption=t.ASK_EXACT_RETURN_DATE, reply_markup=cancel_only_keyboard())


@router.callback_query(F.data == CB_BACK, SearchState.waiting_round_trip)
async def back_from_round_trip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    if data.get("flexible"):
        await state.set_state(SearchState.waiting_departure_range)
        await update_screen(callback=callback, state=state, caption=t.ASK_FLEXIBLE_DEPARTURE_RANGE, reply_markup=cancel_only_keyboard())
    else:
        await state.set_state(SearchState.waiting_departure_date)
        await update_screen(callback=callback, state=state, caption=t.ASK_EXACT_DEPARTURE_DATE, reply_markup=cancel_only_keyboard())


@router.message(SearchState.waiting_return_date)
async def return_date_entered(message, state: FSMContext) -> None:
    data = await state.get_data()
    departure = date.fromisoformat(data["departure_date"])

    try:
        parsed = parse_exact_date(message.text or "")
    except DateInPastError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_IN_PAST_ERROR, reply_markup=cancel_only_keyboard())
        return
    except DateParseError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_PARSE_ERROR, reply_markup=cancel_only_keyboard())
        return

    try:
        validate_return_not_before_departure(departure, parsed)
    except DateRangeOrderError:
        await show_screen(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            caption=t.RETURN_DATE_CONFLICTS_WITH_DEPARTURE,
            reply_markup=cancel_only_keyboard(),
        )
        return

    await state.update_data(return_date=parsed.isoformat())
    await _show_filters(message, state)


@router.message(SearchState.waiting_return_range)
async def return_range_entered(message, state: FSMContext) -> None:
    data = await state.get_data()
    departure_from = date.fromisoformat(data["departure_date_from"])

    try:
        date_range = parse_date_range(message.text or "")
    except DateInPastError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_IN_PAST_ERROR, reply_markup=cancel_only_keyboard())
        return
    except DateRangeOrderError:
        await show_screen(
            bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_RANGE_INVALID_ORDER_ERROR, reply_markup=cancel_only_keyboard()
        )
        return
    except DateParseError:
        await show_screen(
            bot=message.bot, state=state, chat_id=message.chat.id, caption=t.DATE_RANGE_PARSE_ERROR, reply_markup=cancel_only_keyboard()
        )
        return

    try:
        validate_return_not_before_departure(departure_from, date_range.start)
    except DateRangeOrderError:
        await show_screen(
            bot=message.bot,
            state=state,
            chat_id=message.chat.id,
            caption=t.RETURN_DATE_CONFLICTS_WITH_DEPARTURE,
            reply_markup=cancel_only_keyboard(),
        )
        return

    await state.update_data(
        return_date_from=date_range.start.isoformat(), return_date_to=date_range.end.isoformat()
    )
    await _show_filters(message, state)


# --- Filters ---


async def _show_filters(source, state: FSMContext) -> None:
    """source - либо CallbackQuery (переход кнопкой), либо Message (после
    текстового ввода даты) - в обоих случаях экран остаётся фото-подложкой."""
    await state.update_data(direct_only=False, max_price=None)
    await state.set_state(SearchState.waiting_filters)
    keyboard = filters_keyboard(direct_only=False, max_price=None)

    if isinstance(source, CallbackQuery):
        await update_screen(callback=source, state=state, caption=t.ASK_FILTERS, reply_markup=keyboard)
    else:
        await show_screen(
            bot=source.bot, state=state, chat_id=source.chat.id, caption=t.ASK_FILTERS, reply_markup=keyboard
        )


@router.callback_query(F.data == CB_TOGGLE_DIRECT, SearchState.waiting_filters)
async def toggle_direct_only(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    new_value = not data.get("direct_only", False)
    await state.update_data(direct_only=new_value)
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=filters_keyboard(direct_only=new_value, max_price=data.get("max_price"))
    )


@router.callback_query(F.data == CB_SET_MAX_PRICE, SearchState.waiting_filters)
async def ask_max_price(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchState.waiting_max_price)
    await callback.answer()
    await update_screen(callback=callback, state=state, caption=t.ASK_MAX_PRICE, reply_markup=cancel_only_keyboard())


@router.message(SearchState.waiting_max_price)
async def max_price_entered(message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        value = float(raw)
        if value <= 0:
            raise ValueError
    except ValueError:
        await show_screen(bot=message.bot, state=state, chat_id=message.chat.id, caption=t.MAX_PRICE_INVALID, reply_markup=cancel_only_keyboard())
        return

    await state.update_data(max_price=value)
    data = await state.get_data()
    await state.set_state(SearchState.waiting_filters)
    await show_screen(
        bot=message.bot,
        state=state,
        chat_id=message.chat.id,
        caption=t.ASK_FILTERS,
        reply_markup=filters_keyboard(direct_only=data.get("direct_only", False), max_price=value),
    )


@router.callback_query(F.data == CB_RUN_SEARCH, SearchState.waiting_filters)
async def run_search_button(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    await callback.answer()
    await _run_search(callback, state, user, session)


def _build_search_params(data: dict) -> SearchParams:
    return SearchParams(
        origin=data["origin"],
        destination=data["destination"],
        flexible=data.get("flexible", False),
        departure_date=date.fromisoformat(data["departure_date"]) if data.get("departure_date") else None,
        departure_date_from=(
            date.fromisoformat(data["departure_date_from"]) if data.get("departure_date_from") else None
        ),
        departure_date_to=(
            date.fromisoformat(data["departure_date_to"]) if data.get("departure_date_to") else None
        ),
        return_date=date.fromisoformat(data["return_date"]) if data.get("return_date") else None,
        return_date_from=(
            date.fromisoformat(data["return_date_from"]) if data.get("return_date_from") else None
        ),
        return_date_to=date.fromisoformat(data["return_date_to"]) if data.get("return_date_to") else None,
        direct_only=data.get("direct_only", False),
        max_price=data.get("max_price"),
        currency=data.get("currency", "USD"),
    )


async def _run_search(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    data = await state.get_data()
    params = _build_search_params(data)
    chat_id = callback.message.chat.id

    date_display = (
        format_date_ru(params.departure_date)
        if params.departure_date
        else f"{format_date_ru(params.departure_date_from)}-{format_date_ru(params.departure_date_to)}"
    )
    await update_screen(
        callback=callback,
        state=state,
        caption=t.SEARCHING.format(
            origin=data.get("origin_name", params.origin),
            destination=data.get("destination_name", params.destination),
            date=date_display,
        ),
    )

    try:
        results = await search_service.search(params)
    except FlightSearchError:
        await show_screen(bot=callback.bot, state=state, chat_id=chat_id, caption=t.SEARCH_API_ERROR)
        return

    await FlightRepository(session).add_search(
        user_id=user.id,
        origin=params.origin,
        destination=params.destination,
        departure_date=params.departure_date or params.departure_date_from,
        return_date=params.return_date or params.return_date_from,
        flexible=params.flexible,
        filters={"direct_only": params.direct_only, "max_price": params.max_price},
    )

    if not results:
        await state.set_state(SearchState.viewing_results)
        await state.update_data(results=[])
        await show_screen(
            bot=callback.bot, state=state, chat_id=chat_id, caption=t.NO_RESULTS, reply_markup=no_results_keyboard()
        )
        return

    within_budget = results
    if params.max_price is not None:
        within_budget = [r for r in results if r.price <= params.max_price]

    if not within_budget:
        cheapest = search_service.cheapest(results)
        await state.set_state(SearchState.viewing_results)
        await state.update_data(results=[])
        await show_screen(
            bot=callback.bot,
            state=state,
            chat_id=chat_id,
            caption=t.OVER_BUDGET_RESULTS.format(
                cheapest_price=f"{cheapest.price:.0f}", currency=cheapest.currency
            ),
            reply_markup=over_budget_keyboard(),
        )
        return

    limited_results = within_budget[:10]
    persisted = await search_service.persist_results(session, limited_results)

    await state.set_state(SearchState.viewing_results)
    await state.update_data(
        results=[flight.id for flight in persisted],
        result_params=data,
    )
    _results_cache[chat_id] = limited_results

    await _render_results_page(bot=callback.bot, state=state, chat_id=chat_id, index=0, as_new_screen=True)


async def _render_results_page(
    *,
    bot,
    state: FSMContext,
    chat_id: int,
    index: int,
    as_new_screen: bool,
    callback: CallbackQuery | None = None,
) -> None:
    """Рендерит одну страницу карусели результатов поиска на фото-экране.

    as_new_screen=True - первый показ после поиска, заменяет предыдущий
    фото-экран (удаляет его, шлёт новое фото). as_new_screen=False -
    навигация ◀️▶️ по уже открытой карусели, редактирует то же фото-сообщение.
    """
    results = _results_cache.get(chat_id, [])
    if not results:
        return

    index = index % len(results)
    flight = results[index]
    booking_url = flight.booking_url or _default_booking_link(flight.origin, flight.destination)
    caption = render_flight_card(flight, city_service, airline_service, airport_service)
    keyboard = flight_card_keyboard(index, len(results), booking_url)

    if as_new_screen:
        await show_screen(bot=bot, state=state, chat_id=chat_id, caption=caption, reply_markup=keyboard)
    else:
        assert callback is not None
        await update_screen(callback=callback, state=state, caption=caption, reply_markup=keyboard)


@router.callback_query(F.data.startswith(f"{CB_PAGE_PREFIX}:{SCREEN_FLIGHT_RESULTS}:"), SearchState.viewing_results)
async def paginate_flight_results(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    await _render_results_page(
        bot=callback.bot,
        state=state,
        chat_id=callback.message.chat.id,
        index=index,
        as_new_screen=False,
        callback=callback,
    )


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    """Кнопка-счётчик страниц ("2/5") в карусели - не должна ничего делать,
    кроме подтверждения тапа (чтобы у Telegram не крутились "часики")."""
    await callback.answer()


# --- No-results / over-budget quick actions ---


@router.callback_query(F.data == CB_NO_RESULTS_CHANGE_DATES)
async def no_results_change_dates(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SearchState.waiting_date_type)
    await update_screen(callback=callback, state=state, caption=t.ASK_DATE_TYPE, reply_markup=date_type_keyboard())


@router.callback_query(F.data == CB_NO_RESULTS_INCREASE_BUDGET)
async def no_results_increase_budget(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SearchState.waiting_max_price)
    await update_screen(callback=callback, state=state, caption=t.ASK_MAX_PRICE, reply_markup=cancel_only_keyboard())


@router.callback_query(F.data == CB_NO_RESULTS_ALLOW_TRANSFERS)
async def no_results_allow_transfers(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    await state.update_data(direct_only=False)
    await callback.answer()
    await _run_search(callback, state, user, session)


@router.callback_query(F.data == CB_NO_RESULTS_TRACK)
async def no_results_track(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    await callback.answer()
    await _create_subscription_from_state(callback, state, user, session)


@router.callback_query(F.data == CB_OVER_BUDGET_TRACK)
async def over_budget_track(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession) -> None:
    await callback.answer()
    await _create_subscription_from_state(callback, state, user, session)


async def _create_subscription_from_state(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    data = await state.get_data()
    params = _build_search_params(data)
    service = SubscriptionService(session)
    try:
        await service.create_subscription(user_id=user.id, params=params)
    except Exception:
        logger.exception("subscription_creation_failed")
        await callback.answer(t.SUBSCRIPTION_CREATION_FAILED, show_alert=True)
        return
    await state.clear()
    await update_screen(
        callback=callback, state=state, caption=t.MAIN_MENU, reply_markup=main_menu_keyboard()
    )
    await callback.answer(t.SUBSCRIPTION_TRACKING_STARTED, show_alert=True)


# --- Flight card actions: track price ---
# "Купить билет" больше не отдельный хендлер - это прямая URL-кнопка,
# вшитая в flight_card_keyboard(), Telegram открывает её без участия бота.


@router.callback_query(F.data.startswith(f"{CB_TRACK_PREFIX}:"), SearchState.viewing_results)
async def track_ticket(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    index = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    flight_ids = data.get("results", [])
    if index >= len(flight_ids):
        await callback.answer(t.FLIGHT_NOT_FOUND, show_alert=True)
        return

    flight = await FlightRepository(session).get_by_id(flight_ids[index])
    result_params = data.get("result_params", data)
    params = _build_search_params(result_params)

    service = SubscriptionService(session)
    try:
        await service.create_subscription(
            user_id=user.id,
            params=params,
            initial_price=float(flight.price) if flight else None,
            initial_flight_id=flight.id if flight else None,
        )
    except Exception:
        logger.exception("subscription_creation_failed")
        await callback.answer(t.SUBSCRIPTION_CREATION_FAILED, show_alert=True)
        return

    await callback.answer(t.SUBSCRIPTION_TRACKING_STARTED, show_alert=True)
