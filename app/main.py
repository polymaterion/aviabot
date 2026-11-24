from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.handlers import admin, search, settings as settings_handlers, start, subscriptions
from app.bot.middlewares.db import DatabaseMiddleware
from app.config.settings import get_settings
from app.logging_config import setup_logging
from app.scheduler.monitoring import setup_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("bot_starting")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.middleware(DatabaseMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(subscriptions.router)
    dp.include_router(settings_handlers.router)

    scheduler = setup_scheduler(
        bot,
        search.search_service,
        dp.storage,
        search.city_service,
        search.airport_service,
        search.affiliate_service,
    )
    scheduler.start()
    logger.info(
        "monitoring_scheduler_started",
        extra={"interval_minutes": settings.monitoring_interval_minutes},
    )

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("bot_polling_started")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("bot_stopped")


if __name__ == "__main__":
    asyncio.run(main())
