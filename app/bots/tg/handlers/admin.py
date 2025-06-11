"""Handlers for admin commands."""

from __future__ import annotations


from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bots.tg.middlewares.access import AdminAccessMiddleware
from app.bots.tg.states import TenantManagement
from app.core.repositories.tenant import TenantRepository

router = Router(name=__name__)

router.message.middleware(AdminAccessMiddleware())
router.callback_query.middleware(AdminAccessMiddleware())


# --- Tenant Creation FSM ---
@router.message(Command("new_tenant"))
async def handle_new_tenant(message: Message, state: FSMContext):
    """Starts the process of creating a new tenant."""
    await state.set_state(TenantManagement.enter_name)
    await message.answer("Введите имя нового арендатора:")


@router.message(TenantManagement.enter_name)
async def handle_tenant_name(message: Message, state: FSMContext):
    """Handles the new tenant's name and saves it."""
    if not message.text:
        await message.answer("Имя не может быть пустым. Попробуйте еще раз.")
        return

    tenant_name = message.text
    tenant, created = await TenantRepository().get_or_create(name=tenant_name)

    if not created:
        await message.answer(f"Арендатор с именем '{tenant_name}' уже существует.")
    else:
        await message.answer(f"Арендатор '{tenant.name}' успешно создан.")

    await state.clear()


# --- Tariff Creation FSM (to be implemented) ---
@router.message(Command("new_tariff"))
async def handle_new_tariff(message: Message):
    """Placeholder for the new tariff creation process."""
    # TODO: Implement FSM for tariff creation
    await message.answer("Функционал добавления тарифа в разработке.")
