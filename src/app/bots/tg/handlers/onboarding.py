from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import StateFilter, CommandStart

from app.bots.tg.keyboards.reply import get_main_menu
from app.bots.tg.states import Onboarding
from app.config import settings

router = Router(name=__name__)


def _get_onboarding_content(page: int) -> tuple[str, InlineKeyboardBuilder]:
    """Prepares content for an onboarding page."""
    texts = {
        1: (
            "👋 <b>Добро пожаловать в WattWise!</b>\n\n"
            "Этот бот поможет автоматизировать учёт энергоресурсов "
            "и выставление счетов."
        ),
        2: (
            "📊 <b>Как это работает?</b>\n\n"
            "1. Вводите ежемесячные показания.\n"
            "2. Бот сам считает расход и формирует PDF-счёт.\n"
            "3. При необходимости поддерживает суб-счётчики и корректировки."
        ),
        3: ("🚀 <b>Готовы начать?</b>\n\n" "Нажмите кнопку ниже — и вперёд!"),
    }

    builder = InlineKeyboardBuilder()
    if page < 3:
        builder.add(
            InlineKeyboardButton(text="Далее ➡️", callback_data=f"onb_next:{page}")
        )
    else:
        builder.add(InlineKeyboardButton(text="Погнали! 🚀", callback_data="onb_done"))

    return texts[page], builder


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    """Handler for the /start command."""
    if not message.from_user:
        return

    await state.set_state(Onboarding.page1)
    text, builder = _get_onboarding_content(1)
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(
    StateFilter(Onboarding.page1, Onboarding.page2), F.data.startswith("onb_next:")
)
async def onboarding_next(query: CallbackQuery, state: FSMContext):
    if not isinstance(query.message, Message) or not query.data:
        return

    page = int(query.data.split(":")[1]) + 1
    if page == 2:
        await state.set_state(Onboarding.page2)
    else:
        await state.set_state(Onboarding.page3)

    text, builder = _get_onboarding_content(page)
    await query.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(Onboarding.page3, F.data == "onb_done")
async def onboarding_done(query: CallbackQuery, state: FSMContext):
    if not isinstance(query.message, Message) or not query.from_user:
        return

    await state.clear()
    await query.message.edit_text("✅ Настройка завершена!")

    is_admin = query.from_user.id in settings.ADMIN_IDS
    await query.message.answer("Главное меню:", reply_markup=get_main_menu(is_admin))
