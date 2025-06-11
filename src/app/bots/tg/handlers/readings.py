"""Handlers for the reading entry process (FSM)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dateutil.relativedelta import relativedelta

from app.bots.tg.keyboards.inline import SelectMeterCallback, SelectTenantCallback
from app.bots.tg.states import ReadingEntry
from app.core.repositories.meter import MeterRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tenant import TenantRepository

router = Router(name=__name__)


@router.message(F.text == "✍️ Ввести показания")
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
                callback_data=SelectTenantCallback(tenant_id=str(tenant.id)).pack(),
            )
        )
    await message.answer(
        "Выберите арендатора для ввода показаний:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(SelectTenantCallback.filter())
async def handle_tenant_selection(
    query: CallbackQuery, callback_data: SelectTenantCallback
):
    """Handles tenant selection and shows their meters."""
    if not isinstance(query.message, Message):
        return

    tenant_id = callback_data.tenant_id
    meters = await MeterRepository().get_for_tenant(tenant_id)

    if not meters:
        await query.message.edit_text("У этого арендатора нет счетчиков.")
        return

    builder = InlineKeyboardBuilder()
    for meter in meters:
        builder.row(
            InlineKeyboardButton(
                text=meter.name,
                callback_data=SelectMeterCallback(id=str(meter.id)).pack(),
            )
        )
    await query.message.edit_text("Выберите счетчик:", reply_markup=builder.as_markup())


@router.callback_query(SelectMeterCallback.filter())
async def handle_meter_selection(
    query: CallbackQuery, callback_data: SelectMeterCallback, state: FSMContext
):
    """
    Handles meter selection. If it's the first time a reading is entered,
    it asks for the previous month's value first. Otherwise, it asks for
    the current value.
    """
    if not isinstance(query.message, Message):
        return

    # Fetch selected meter with parent info
    meter_repo = MeterRepository()
    meter = await meter_repo.model.get(id=callback_data.id)

    await state.update_data(
        meter_id=str(meter.id),
        meter_name=meter.name,
        is_sub=bool(meter.subtract_from),
    )

    # Check for previous month's reading to decide the flow
    repo = ReadingRepository()
    current_period = date.today().replace(day=1)
    prev_period = current_period - relativedelta(months=1)
    previous_reading = await repo.model.filter(
        meter_id=callback_data.id, period=prev_period
    ).first()

    if previous_reading:
        # Normal flow: previous reading exists
        await state.update_data(prev_value=str(previous_reading.value))
        await state.set_state(ReadingEntry.enter_value)

        if meter.subtract_from:
            warn_sub = (
                "\n⚠️ Этот счётчик является под-счётчиком. "
                "Расход родительского будет скорректирован."
            )
        else:
            warn_sub = ""

        await query.message.edit_text(
            "Показание за <b>{:%B %Y}</b>: <b>{}</b>{}"
            "\n\nВведите текущее показание:".format(
                prev_period, previous_reading.value, warn_sub
            )
        )
    else:
        # First-time entry flow: no previous reading
        await state.set_state(ReadingEntry.enter_previous_value)
        await query.message.edit_text(
            "Похоже, вы впервые вводите показания для этого счетчика.\n"
            "Чтобы рассчитать расход, мне нужны данные за прошлый месяц.\n\n"
            f"Пожалуйста, введите показание за <b>{prev_period:%B %Y}</b>:"
        )


@router.message(ReadingEntry.enter_previous_value)
async def handle_previous_reading_value(message: Message, state: FSMContext):
    """Handles the previous month's reading and asks for the current one."""
    if not message.text:
        return
    try:
        value = Decimal(message.text)
    except InvalidOperation:
        await message.answer("Неверный формат. Пожалуйста, введите число.")
        return

    await state.update_data(previous_value=value)
    await state.set_state(ReadingEntry.enter_value)
    current_period = date.today().replace(day=1)
    await message.answer(
        "Отлично! А теперь введите показание за " f"<b>{current_period:%B %Y}</b>:"
    )


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
    data = await state.get_data()

    # Reconstruct periods for confirmation block
    current_period = date.today().replace(day=1)
    prev_period = current_period - relativedelta(months=1)

    if "prev_value" in data or "previous_value" in data:
        prev_val = Decimal(str(data.get("previous_value", data.get("prev_value"))))
        diff = value - prev_val

        text = (
            "<b>Проверьте введенные данные:</b>\n"
            f"Показание за {prev_period:%B %Y}: <b>{prev_val}</b>\n"
            f"Показание за {current_period:%B %Y}: <b>{value}</b>\n"
            f"Расход за месяц: <b>{diff}</b> кВт·ч\n\n"
            "Все верно?"
        )
    else:
        text = f"Вы ввели: {value}. Подтверждаете?"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(ReadingEntry.confirm_entry)


@router.callback_query(ReadingEntry.confirm_entry, F.data == "confirm")
async def handle_confirmation(query: CallbackQuery, state: FSMContext):
    """Handles confirmation, saves the reading(s), and ends the FSM."""
    if not isinstance(query.message, Message):
        return

    data = await state.get_data()
    repo = ReadingRepository()
    current_period = date.today().replace(day=1)

    # Save previous reading if it was entered
    if "previous_value" in data:
        prev_period = current_period - relativedelta(months=1)
        await repo.update_or_create(
            defaults={"value": data["previous_value"]},
            meter_id=data["meter_id"],
            period=prev_period,
        )

    # Save current reading
    _, created = await repo.update_or_create(
        defaults={"value": data["current_value"]},
        meter_id=data["meter_id"],
        period=current_period,
    )

    if "previous_value" in data:
        await query.message.edit_text("✅ Отлично! Оба показания сохранены.")
    elif created:
        await query.message.edit_text("✅ Показание успешно сохранено!")
    else:
        await query.message.edit_text("✅ Показание успешно обновлено!")
    await state.clear()


@router.callback_query(ReadingEntry.confirm_entry, F.data == "cancel")
async def handle_cancellation(query: CallbackQuery, state: FSMContext):
    """Handles cancellation and ends the FSM."""
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text("Действие отменено.")
    await state.clear()
