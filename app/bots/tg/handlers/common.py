"""Common command handlers."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name=__name__)


@router.message(CommandStart())
async def handle_start(message: Message):
    """Handler for the /start command."""
    await message.answer(
        "Добро пожаловать в WattWise Bot!\n\n"
        "Доступные команды:\n"
        "/readings - Начать ввод показаний\n"
        "/invoice - Сформировать счет за период"
    )


@router.message(commands=["help"])
async def handle_help(message: Message):
    """Handler for the /help command."""
    await message.answer(
        "Этот бот помогает управлять показаниями счетчиков и счетами.\n\n"
        "Используйте /start для просмотра основных команд."
    )
