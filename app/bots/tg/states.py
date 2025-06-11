"""FSM states for the bot."""

from aiogram.fsm.state import State, StatesGroup


class ReadingEntry(StatesGroup):
    """States for the meter reading entry process."""

    enter_value = State()
    confirm_entry = State()
