"""Inline keyboard builders."""

from aiogram.filters.callback_data import CallbackData


class TenantCallbackFactory(CallbackData, prefix="tenant"):
    """Callback data for selecting a tenant."""

    id: str


class MeterCallbackFactory(CallbackData, prefix="meter"):
    """Callback data for selecting a meter."""

    id: str
