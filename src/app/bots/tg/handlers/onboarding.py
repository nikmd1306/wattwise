from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.tg.keyboards.reply import get_main_menu
from app.bots.tg.states import Onboarding
from app.config import settings

router = Router(name=__name__)


async def _send_page(message: Message, page: int):
    """Utility: send onboarding page with navigation buttons."""
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

    await message.answer(texts[page], reply_markup=builder.as_markup())


@router.message(F.text == "/onboarding")
async def start_onboarding_manual(message: Message, state: FSMContext):
    """Manual command to start onboarding (for tests)."""
    await state.set_state(Onboarding.page1)
    await _send_page(message, 1)


@router.callback_query(F.data.startswith("onb_next:"))
async def onboarding_next(query: CallbackQuery, state: FSMContext):
    if not isinstance(query.message, Message):
        return
    if not query.data:
        return
    page = int(query.data.split(":")[1]) + 1
    if page == 2:
        await state.set_state(Onboarding.page2)
    else:
        await state.set_state(Onboarding.page3)
    await _send_page(query.message, page)


@router.callback_query(F.data == "onb_done")
async def onboarding_done(query: CallbackQuery, state: FSMContext):
    if not isinstance(query.message, Message):
        return
    await state.clear()
    # Show main menu
    if not query.from_user:
        return
    is_admin = query.from_user.id in settings.ADMIN_IDS
    await query.message.answer("Главное меню:", reply_markup=get_main_menu(is_admin))
