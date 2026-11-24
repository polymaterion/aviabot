from __future__ import annotations

import logging
from collections import defaultdict

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config.settings import get_settings
from app.database.models import Subscription
from app.database.repositories.subscription_repository import SubscriptionRepository
from app.database.session import get_session
from app.providers.base import FlightResult
from app.services.affiliate_service import AffiliateService
from app.services.airport_service import AirportService
from app.services.notification_service import NotificationService
from app.services.search_key import SearchParams, build_search_key
from app.services.search_service import FlightSearchError, SearchService

logger = logging.getLogger(__name__)


def _subscription_to_params(sub: Subscription) -> SearchParams:
    return SearchParams(
        origin=sub.origin,
        destination=sub.destination,
        flexible=sub.flexible,
        departure_date=sub.departure_date,
        departure_date_from=sub.departure_date_from,
        departure_date_to=sub.departure_date_to,
        return_date=sub.return_date,
        return_date_from=sub.return_date_from,
        return_date_to=sub.return_date_to,
        direct_only=sub.direct_only,
        max_price=None,  # групповой API-запрос без ограничения цены; фильтрация - per-subscription ниже
        currency=sub.currency,
    )


async def run_monitoring_cycle(
    bot: Bot,
    search_service: SearchService,
    storage: BaseStorage,
    city_service,
    airport_service: AirportService,
    affiliate_service: AffiliateService,
) -> None:
    """Один цикл мониторинга (п.32-33 ТЗ):

    1. Собрать все активные подписки.
    2. Сгруппировать их по нормализованному search_key (без учёта max_price).
    3. Выполнить ОДИН запрос к провайдеру на каждую уникальную группу.
    4. Для каждой подписки в группе применить её собственный max_price/direct_only
       фильтр к общим результатам и решить, нужно ли уведомление.
    """
    async with get_session() as session:
        repo = SubscriptionRepository(session)
        active_subscriptions = await repo.list_active()

        if not active_subscriptions:
            logger.info("monitoring_cycle_no_active_subscriptions")
            return

        groups: dict[str, list[Subscription]] = defaultdict(list)
        params_by_key: dict[str, SearchParams] = {}

        for sub in active_subscriptions:
            params = _subscription_to_params(sub)
            key = build_search_key(params)
            groups[key].append(sub)
            params_by_key[key] = params

        logger.info(
            "monitoring_cycle_grouped",
            extra={"subscriptions": len(active_subscriptions), "unique_searches": len(groups)},
        )

        notification_service = NotificationService(
            bot,
            session,
            storage,
            city_service,
            airport_service,
            affiliate_service,
            threshold_resolver=get_settings().price_drop_threshold_for,
        )

        for key, subs in groups.items():
            params = params_by_key[key]
            try:
                results = await search_service.search(params)
            except FlightSearchError:
                logger.warning("monitoring_group_search_failed", extra={"search_key": key})
                continue

            persisted_flights = await search_service.persist_results(session, results[:20])
            flight_by_external_id = {f.external_id: f for f in persisted_flights}

            for sub in subs:
                await _process_subscription(
                    sub, results, flight_by_external_id, notification_service
                )


async def _process_subscription(
    subscription: Subscription,
    results: list[FlightResult],
    flight_by_external_id: dict,
    notification_service: NotificationService,
) -> None:
    filtered = results
    if subscription.direct_only:
        filtered = [r for r in filtered if r.direct]
    if subscription.max_price is not None:
        filtered = [r for r in filtered if r.price <= float(subscription.max_price)]

    best = min(filtered, key=lambda r: r.price) if filtered else None
    flight_id = None
    if best is not None:
        flight_row = flight_by_external_id.get(best.external_id)
        flight_id = flight_row.id if flight_row else None

    telegram_id = subscription.user.telegram_id
    notifications_enabled = subscription.user.notifications_enabled

    await notification_service.process_subscription_result(
        subscription, best, flight_id, telegram_id, notifications_enabled
    )


def setup_scheduler(
    bot: Bot,
    search_service: SearchService,
    storage: BaseStorage,
    city_service,
    airport_service: AirportService,
    affiliate_service: AffiliateService,
) -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_monitoring_cycle,
        trigger=IntervalTrigger(minutes=settings.monitoring_interval_minutes),
        args=[bot, search_service, storage, city_service, airport_service, affiliate_service],
        id="price_monitoring",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
