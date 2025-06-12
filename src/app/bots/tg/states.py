"""FSM states for the bot."""

from aiogram.fsm.state import State, StatesGroup


class ReadingEntry(StatesGroup):
    """States for the meter reading entry process."""

    enter_previous_value = State()
    enter_value = State()
    enter_adjustment = State()
    confirm_entry = State()


class TenantManagement(StatesGroup):
    """States for tenant management."""

    enter_name = State()


class TariffManagement(StatesGroup):
    """States for tariff management."""

    select_tenant = State()
    select_meter = State()
    manage_existing = State()
    enter_name = State()
    enter_rate = State()
    enter_start_date = State()
    confirm_creation = State()


class MeterManagement(StatesGroup):
    """States for meter management."""

    select_tenant = State()
    enter_name = State()
    ask_is_submeter = State()
    select_parent_meter = State()


class DeductionLinkManagement(StatesGroup):
    """States for deduction link management."""

    start = State()
    select_parent_tenant = State()
    select_parent_meter = State()
    select_child_tenant = State()
    select_child_meter = State()
    enter_description = State()
    confirm_creation = State()


class Onboarding(StatesGroup):
    """States for the onboarding carousel."""

    page1 = State()
    page2 = State()
    page3 = State()
