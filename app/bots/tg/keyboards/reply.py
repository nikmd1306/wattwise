"""Reply keyboard builders."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Builds the main menu reply keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✍️ Ввести показания"),
        KeyboardButton(text="📄 Получить счет"),
    )
    if is_admin:
        builder.row(KeyboardButton(text="⚙️ Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def get_admin_panel() -> ReplyKeyboardMarkup:
    """Builds the admin panel reply keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👤 Создать арендатора"),
        KeyboardButton(text="📟 Добавить счетчик"),
    )
    builder.row(
        KeyboardButton(text="📈 Создать тариф"),
    )
    builder.row(KeyboardButton(text="⬅️ Назад в главное меню"))
    return builder.as_markup(resize_keyboard=True)
