"""Main entry point for the Telegram bot."""

import asyncio
import logging
import locale

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from tortoise import Tortoise

from app.config import settings
from app.core.db import TORTOISE_ORM
from app.bots.tg.handlers import (
    readings,
    invoices,
    admin,
    summary,
    onboarding,
    deductions,
    common,
)
from app.services.billing import BillingService
from app.core.repositories.tenant import TenantRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tariff import TariffRepository
from app.core.repositories.invoice import InvoiceRepository


logger = logging.getLogger(__name__)


async def on_startup(dispatcher: Dispatcher, bot: Bot):
    """Actions on bot startup."""
    logger.info("Initializing database...")
    await Tortoise.init(config=TORTOISE_ORM)
    logger.info("Database initialized.")

    billing_service = BillingService(
        tenant_repo=TenantRepository(),
        reading_repo=ReadingRepository(),
        tariff_repo=TariffRepository(),
        invoice_repo=InvoiceRepository(),
    )
    dispatcher["billing_service"] = billing_service
    logger.info("Services injected into dispatcher.")

    logger.info("Deleting webhook and dropping pending updates...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted.")
    logger.info("Bot started.")


async def on_shutdown(bot: Bot):
    """Actions on bot shutdown."""
    logger.info("Closing connections...")
    await Tortoise.close_connections()
    await bot.session.close()
    logger.info("Connections closed.")


async def main():
    """Initializes and starts the bot."""
    try:
        locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
    except locale.Error:
        logger.warning(
            "Locale 'ru_RU.UTF-8' not found. Dates may be displayed in English. "
            "The Dockerfile is configured to install this locale, so this warning "
            "may indicate a problem with the base image or the build process."
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger.info("Starting bot initialization...")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    # Register startup and shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register routers
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(readings.router)
    dp.include_router(invoices.router)
    dp.include_router(admin.router)
    dp.include_router(deductions.router)
    dp.include_router(summary.router)

    await dp.start_polling(bot, dispatcher=dp)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually.")
