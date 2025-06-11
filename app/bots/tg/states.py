"""FSM states for the bot."""

from aiogram.fsm.state import State, StatesGroup


class ReadingEntry(StatesGroup):
    """States for the meter reading entry process."""

    enter_value = State()
    confirm_entry = State()


class TenantManagement(StatesGroup):
    """States for tenant management."""

    enter_name = State()


class TariffManagement(StatesGroup):
    """States for tariff management."""

    select_tenant = State()
    select_meter = State()
    enter_rate = State()
    enter_start_date = State()
