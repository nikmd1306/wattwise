from __future__ import annotations

from datetime import date

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dateutil.relativedelta import relativedelta

from app.bots.tg.keyboards.inline import SelectPeriodCallback
from app.core.dates import format_period_for_display


def get_period_keyboard(action: str) -> InlineKeyboardBuilder:
    """
    Builds an inline keyboard with buttons for the last 6 months.

    Args:
        action: The action to be encoded in the callback data (e.g., 'invoice').

    Returns:
        An InlineKeyboardBuilder with the period buttons.
    """
    builder = InlineKeyboardBuilder()
    today = date.today()

    # Offer last 6 months, including the current one
    for i in range(6):
        period_date = today - relativedelta(months=i)
        # Use custom formatter to avoid locale issues
        month_name = format_period_for_display(period_date)
        callback_data = SelectPeriodCallback(
            action=action, period=period_date.strftime("%Y-%m")
        ).pack()
        builder.row(InlineKeyboardButton(text=month_name, callback_data=callback_data))

    return builder
