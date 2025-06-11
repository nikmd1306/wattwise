"""Main entry point for the Telegram bot."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from tortoise import Tortoise

from app.config import settings
from app.core.db import TORTOISE_ORM
from app.bots.tg.handlers import common, readings

logger = logging.getLogger(__name__)


async def main():
    """Initializes and starts the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger.info("Starting bot...")

    await Tortoise.init(config=TORTOISE_ORM)

    bot = Bot(token=settings.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    # Register routers
    dp.include_router(common.router)
    dp.include_router(readings.router)

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
