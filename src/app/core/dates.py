"""Date and time helper functions."""

from __future__ import annotations

from datetime import date

MONTHS_NOMINATIVE = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def format_period_for_display(period_date: date) -> str:
    """Formats a date period into 'Month YYYY' in Russian nominative case."""
    return f"{MONTHS_NOMINATIVE[period_date.month]} {period_date.year}"


def format_period_for_title(period_date: date) -> str:
    """Formats a date period into 'month YYYY' in Russian genitive case."""
    return f"{MONTHS_GENITIVE[period_date.month]} {period_date.year}"
