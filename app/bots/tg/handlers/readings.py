"""Handlers for the reading entry process (FSM)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.tg.keyboards.inline import MeterCallbackFactory, TenantCallbackFactory
from app.bots.tg.states import ReadingEntry
from app.core.repositories.meter import MeterRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tenant import TenantRepository

router = Router(name=__name__)


@router.message(Command("readings"))
async def handle_readings_command(message: Message):
    """Starts the reading entry process by showing a list of tenants."""
    tenants = await TenantRepository().all()
    if not tenants:
        await message.answer("Арендаторы не найдены. Сначала добавьте их.")
        return

    builder = InlineKeyboardBuilder()
    for tenant in tenants:
        builder.row(
            InlineKeyboardButton(
                text=tenant.name,
                callback_data=TenantCallbackFactory(id=str(tenant.id)).pack(),
            )
        )
    await message.answer(
        "Выберите арендатора для ввода показаний:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(TenantCallbackFactory.filter())
async def handle_tenant_selection(
    query: CallbackQuery, callback_data: TenantCallbackFactory
):
    """Handles tenant selection and shows their meters."""
    if not isinstance(query.message, Message):
        return

    tenant_id = callback_data.id
    meters = await MeterRepository().get_for_tenant(tenant_id)

    if not meters:
        await query.message.edit_text("У этого арендатора нет счетчиков.")
        return

    builder = InlineKeyboardBuilder()
    for meter in meters:
        builder.row(
            InlineKeyboardButton(
                text=meter.name,
                callback_data=MeterCallbackFactory(id=str(meter.id)).pack(),
            )
        )
    await query.message.edit_text("Выберите счетчик:", reply_markup=builder.as_markup())


@router.callback_query(MeterCallbackFactory.filter())
async def handle_meter_selection(
    query: CallbackQuery, callback_data: MeterCallbackFactory, state: FSMContext
):
    """Handles meter selection and asks for the reading value."""
    if not isinstance(query.message, Message):
        return

    await state.update_data(meter_id=callback_data.id)
    await state.set_state(ReadingEntry.enter_value)
    await query.message.edit_text("Пожалуйста, введите текущее показание счетчика:")


@router.message(ReadingEntry.enter_value)
async def handle_reading_value(message: Message, state: FSMContext):
    """Handles the entered reading value and asks for confirmation."""
    if not message.text:
        return
    try:
        value = Decimal(message.text)
    except InvalidOperation:
        await message.answer("Неверный формат. Пожалуйста, введите число.")
        return

    await state.update_data(current_value=value)
    # Here we would normally calculate consumption and cost.
    # For now, just ask for confirmation.
    # TODO: Implement calculation logic by calling a service.

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await message.answer(
        f"Вы ввели: {value}. Подтверждаете?", reply_markup=builder.as_markup()
    )
    await state.set_state(ReadingEntry.confirm_entry)


@router.callback_query(ReadingEntry.confirm_entry, F.data == "confirm")
async def handle_confirmation(query: CallbackQuery, state: FSMContext):
    """Handles confirmation, saves the reading, and ends the FSM."""
    if not isinstance(query.message, Message):
        return

    data = await state.get_data()

    # TODO: Use the real period.
    await ReadingRepository().create(
        meter_id=data["meter_id"],
        period="2024-07-01",
        value=data["current_value"],
    )

    await query.message.edit_text("Показание успешно сохранено!")
    await state.clear()


@router.callback_query(ReadingEntry.confirm_entry, F.data == "cancel")
async def handle_cancellation(query: CallbackQuery, state: FSMContext):
    """Handles cancellation and ends the FSM."""
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text("Действие отменено.")
    await state.clear()
