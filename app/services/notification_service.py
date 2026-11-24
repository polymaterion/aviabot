from __future__ import annotations

import logging
from typing import Callable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.screen.manager import notify_and_clear_screen
from app.bot.texts import ru as t
from app.database.models import NotificationType, Subscription
from app.database.repositories.flight_repository import FlightRepository
from app.database.repositories.subscription_repository import SubscriptionRepository
from app.providers.base import FlightResult
from app.services.affiliate_service import AffiliateService
from app.services.airport_service import AirportService
from app.services.date_service import format_date_ru

logger = logging.getLogger(__name__)

# Валюта -> минимальное изменение цены, при котором отправляется
# уведомление о снижении. "300" в рублях и "300" в долларах - совершенно
# разная величина, поэтому порог задаётся отдельно на каждую валюту, а
# не одним универсальным числом.
DEFAULT_PRICE_DROP_THRESHOLDS: dict[str, float] = {"RUB": 300.0, "USD": 5.0, "EUR": 5.0}
DEFAULT_PRICE_DROP_FALLBACK = 5.0


def default_threshold_resolver(currency: str) -> float:
    return DEFAULT_PRICE_DROP_THRESHOLDS.get(currency.upper(), DEFAULT_PRICE_DROP_FALLBACK)


class NotificationService:
    """Отправляет уведомления и защищает от повторных алертов (п.35-36 ТЗ).

    Логика сравнения предыдущего/нового состояния:
    - было недоступно, стало доступно -> "новый билет" или "снова доступен"
      (уведомление отправляется всегда, порог цены здесь не применяется -
      пользователь должен узнать о появлении билета в любом случае);
    - цена снизилась БОЛЬШЕ чем порог для данной валюты -> "цена снизилась";
    - цена снизилась незначительно, не изменилась или выросла -> без
      уведомления, чтобы не заваливать пользователя уведомлениями о
      колебаниях цены на несколько рублей/долларов.

    Перед отправкой уведомления удаляется текущий системный фото-экран
    пользователя (если он был открыт), чтобы в чате не копились старые
    меню поверх уведомлений. Само уведомление НЕ удаляется никогда -
    остаётся в чате как история цен.
    """

    def __init__(
        self,
        bot: Bot,
        session: AsyncSession,
        storage: BaseStorage,
        city_service,
        airport_service: AirportService,
        affiliate_service: AffiliateService,
        threshold_resolver: Callable[[str], float] = default_threshold_resolver,
    ) -> None:
        self._bot = bot
        self._session = session
        self._storage = storage
        self._city_service = city_service
        self._airport_service = airport_service
        self._affiliate_service = affiliate_service
        self._flight_repo = FlightRepository(session)
        self._subscription_repo = SubscriptionRepository(session)
        self._threshold_resolver = threshold_resolver

    async def process_subscription_result(
        self,
        subscription: Subscription,
        best_result: FlightResult | None,
        flight_id: int | None,
        telegram_id: int,
        notifications_enabled: bool,
    ) -> None:
        was_available = subscription.last_seen_available
        previous_price = subscription.last_known_price

        if best_result is None:
            # Ничего подходящего не найдено сейчас - просто фиксируем состояние.
            await self._subscription_repo.update_last_known_state(
                subscription, price=None, flight_id=None, available=False
            )
            return

        new_price = best_result.price
        date_str = (
            format_date_ru(best_result.departure_datetime.date())
            if best_result.departure_datetime
            else "-"
        )

        notification_type: NotificationType | None = None

        if not was_available:
            notification_type = (
                NotificationType.FLIGHT_BACK if previous_price is not None else NotificationType.NEW_FLIGHT
            )
        elif previous_price is not None:
            threshold = self._threshold_resolver(best_result.currency)
            if (previous_price - new_price) > threshold:
                notification_type = NotificationType.PRICE_DROP
        # else: цена не изменилась, выросла, или снизилась незначительно
        # (меньше порога для данной валюты) -> без уведомления (п.36 ТЗ)

        await self._flight_repo.record_price_history(
            flight_id=flight_id,
            subscription_id=subscription.id,
            price=new_price,
            currency=best_result.currency,
        )

        await self._subscription_repo.update_last_known_state(
            subscription, price=new_price, flight_id=flight_id, available=True
        )

        if notification_type is None:
            return

        if notifications_enabled:
            await self._send_notification(
                telegram_id=telegram_id,
                notification_type=notification_type,
                flight=best_result,
                date_str=date_str,
                price=new_price,
                previous_price=previous_price,
            )

        await self._flight_repo.add_notification(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            flight_id=flight_id,
            type_=notification_type,
            price=new_price,
        )

    def _resolve_city_name(self, iata: str) -> str:
        city = self._city_service.get_by_iata(iata)
        if city is not None:
            return city.name
        return self._airport_service.city_name(iata)

    def _buy_button(self, flight: FlightResult) -> InlineKeyboardMarkup:
        """Кнопка «Купить билет» под уведомлением - ссылка ведёт именно
        на ЭТОТ билет (booking_url конкретного результата), а не на общий
        поиск по маршруту."""
        booking_url = flight.booking_url or self._affiliate_service.build_search_link(
            origin=flight.origin, destination=flight.destination
        )
        builder = InlineKeyboardBuilder()
        builder.button(text=t.BTN_BUY_TICKET, url=booking_url)
        return builder.as_markup()

    async def _send_notification(
        self,
        *,
        telegram_id: int,
        notification_type: NotificationType,
        flight: FlightResult,
        date_str: str,
        price: float,
        previous_price: float | None,
    ) -> None:
        origin_name = self._resolve_city_name(flight.origin)
        destination_name = self._resolve_city_name(flight.destination)
        currency = flight.currency

        if notification_type == NotificationType.NEW_FLIGHT:
            text = t.NOTIFY_NEW_FLIGHT.format(
                origin=origin_name, destination=destination_name, date=date_str, price=price, currency=currency
            )
        elif notification_type == NotificationType.PRICE_DROP:
            text = t.NOTIFY_PRICE_DROP.format(
                origin=origin_name,
                destination=destination_name,
                date=date_str,
                old_price=previous_price,
                new_price=price,
                currency=currency,
            )
        else:
            text = t.NOTIFY_FLIGHT_BACK.format(
                origin=origin_name, destination=destination_name, date=date_str, price=price, currency=currency
            )

        try:
            state = FSMContext(
                storage=self._storage,
                key=StorageKey(bot_id=self._bot.id, chat_id=telegram_id, user_id=telegram_id),
            )
            await notify_and_clear_screen(
                bot=self._bot,
                state=state,
                chat_id=telegram_id,
                text=text,
                reply_markup=self._buy_button(flight),
            )
        except TelegramAPIError as exc:
            logger.warning(
                "notification_send_failed", extra={"telegram_id": telegram_id, "error": str(exc)}
            )
