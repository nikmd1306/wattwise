"""Common command handlers."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bots.tg.keyboards.reply import get_admin_panel, get_main_menu
from app.config import settings

router = Router(name=__name__)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Handler for the /help command."""
    await message.answer(
        "Этот бот помогает управлять показаниями счетчиков и счетами.\n\n"
        "Используйте клавиатуру ниже для навигации."
    )


@router.message(F.text == "⚙️ Админ-панель")
async def handle_admin_panel(message: Message) -> None:
    """Shows the admin panel."""
    await message.answer("Админ-панель:", reply_markup=get_admin_panel())


@router.message(F.text == "⬅️ Назад в главное меню")
async def handle_back_to_main_menu(message: Message) -> None:
    """Returns the user to the main menu."""
    if not message.from_user:
        return
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu(message.from_user.id in settings.ADMIN_IDS),
    )
