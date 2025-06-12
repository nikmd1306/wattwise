"""Main entry point for the Telegram bot."""

import asyncio
import logging
import locale

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from tortoise import Tortoise

from app.config import settings
from app.core.db import TORTOISE_ORM
from app.bots.tg.handlers import readings, invoices, admin, summary, onboarding
from app.services.billing import BillingService
from app.core.repositories.tenant import TenantRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tariff import TariffRepository
from app.core.repositories.invoice import InvoiceRepository
from app.bots.tg.handlers import common

logger = logging.getLogger(__name__)


async def main():
    """Initializes and starts the bot."""
    try:
        locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
    except locale.Error:
        logger.warning(
            "Locale 'ru_RU.UTF-8' not found. Dates will be in English. "
            "To fix, install the locale on your system (e.g., on Debian/Ubuntu: "
            "'sudo apt-get install -y language-pack-ru' and 'sudo update-locale')."
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger.info("Starting bot...")

    await Tortoise.init(config=TORTOISE_ORM)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    # Register routers
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(readings.router)
    dp.include_router(invoices.router)
    dp.include_router(admin.router)
    dp.include_router(summary.router)

    # Pass services to handlers
    billing_service = BillingService(
        tenant_repo=TenantRepository(),
        reading_repo=ReadingRepository(),
        tariff_repo=TariffRepository(),
        invoice_repo=InvoiceRepository(),
    )
    dp["billing_service"] = billing_service

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await Tortoise.close_connections()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
