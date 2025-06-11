"""Middleware for access control."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.config import settings


class AdminAccessMiddleware(BaseMiddleware):
    """
    Checks if the user is in the admin list before processing an update.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return None

        if user.id in settings.ADMIN_IDS:
            return await handler(event, data)

        return None
