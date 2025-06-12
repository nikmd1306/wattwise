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
from app.core.models import DeductionLink
from app.core.repositories.meter import MeterRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tariff import TariffRepository
from app.core.repositories.tenant import TenantRepository

router = Router(name=__name__)


@router.message(F.text == "✍️ Ввести показания")
async def handle_readings_command(message: Message) -> None:
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
) -> None:
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
) -> None:
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

    await state.update_data(meter_id=str(meter.id), meter_name=meter.name)

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

        await query.message.edit_text(
            "Показание за <b>{:%B %Y}</b>: <b>{:.0f}</b>"
            "\n\nВведите текущее показание:".format(prev_period, previous_reading.value)
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
async def handle_previous_reading_value(message: Message, state: FSMContext) -> None:
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


async def _check_for_deductions_and_proceed(
    message: Message, state: FSMContext
) -> None:
    """
    Checks if the current meter has deduction links. If so, prompts the user
    for an adjustment. Otherwise, proceeds directly to confirmation.
    """
    data = await state.get_data()
    meter_id = data["meter_id"]

    deduction_link = await DeductionLink.filter(parent_meter_id=meter_id).first()
    if not deduction_link:
        await _show_confirmation(message, state)
        return

    await deduction_link.fetch_related("child_meter__tenant")
    child_meter = deduction_link.child_meter

    # Calculate consumption for the child meter to suggest it
    current_period = date.today().replace(day=1)
    prev_period = current_period - relativedelta(months=1)
    reading_repo = ReadingRepository()
    child_curr = await reading_repo.model.get_or_none(
        meter_id=child_meter.id, period=current_period
    )
    child_prev = await reading_repo.model.get_or_none(
        meter_id=child_meter.id, period=prev_period
    )

    suggestion = None
    if child_curr and child_prev:
        suggestion = child_curr.value - child_prev.value

    # Get tariff for context
    tariff_repo = TariffRepository()
    tariff = await tariff_repo.find_for_date(child_meter.id, current_period)
    tariff_info = f"{tariff.rate:.2f} ₽" if tariff else "нет тарифа"

    text_lines = [
        "💬 <b>Требуется корректировка.</b>",
        f"Из этого счётчика нужно вычесть показания "
        f"по правилу «{deduction_link.description}».",
    ]
    if suggestion is not None:
        child_tenant_name = child_meter.tenant.name
        child_meter_name = child_meter.name
        text_lines.append(
            f"<i>Источник: «{child_meter_name}» ({child_tenant_name})</i>"
        )
        text_lines.append(
            f"Расход по нему (тариф {tariff_info}): <b>{suggestion:.0f} кВт·ч</b>."
        )

    text_lines.append("\n<b>Какое значение вычесть?</b> Отправьте цифру в кВт·ч.")

    builder = InlineKeyboardBuilder()
    if suggestion is not None:
        builder.row(
            InlineKeyboardButton(
                text=f"Вычесть {suggestion:.0f} кВт·ч",
                callback_data=f"adj:{suggestion}",
            )
        )

    await message.answer("\n".join(text_lines), reply_markup=builder.as_markup())
    await state.set_state(ReadingEntry.enter_adjustment)


async def _show_confirmation(
    message: Message, state: FSMContext, adjustment: Decimal | None = None
) -> None:
    """Shows the final confirmation message to the user."""
    await state.update_data(manual_adjustment=str(adjustment or Decimal("0")))
    data = await state.get_data()

    current_period = date.today().replace(day=1)
    prev_period = current_period - relativedelta(months=1)
    prev_val = Decimal(str(data.get("previous_value", data.get("prev_value"))))
    current_val = Decimal(data["current_value"])
    diff = current_val - prev_val

    text_lines = ["<b>Проверьте введенные данные:</b>"]
    text_lines.append(f"Показание за {prev_period:%B %Y}: <b>{prev_val:.0f}</b>")
    text_lines.append(f"Показание за {current_period:%B %Y}: <b>{current_val:.0f}</b>")
    text_lines.append(f"Расход за месяц: <b>{diff:.0f}</b> кВт·ч")

    if adjustment and adjustment > 0:
        text_lines.append(f"Ручная корректировка: <b>-{adjustment:.0f} кВт·ч</b>")
        final_consumption = diff - adjustment
        text_lines.append(
            f"✅ <b>Итоговый расход к учёту: {final_consumption:.0f} кВт·ч</b>"
        )

    text_lines.append("\nВсе верно?")
    text = "\n".join(text_lines)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(ReadingEntry.confirm_entry)


@router.message(ReadingEntry.enter_value)
async def handle_reading_value(message: Message, state: FSMContext) -> None:
    """Handles the entered reading value and checks for deductions."""
    if not message.text:
        return
    try:
        value = Decimal(message.text)
    except InvalidOperation:
        await message.answer("Неверный формат. Пожалуйста, введите число.")
        return

    await state.update_data(current_value=str(value))
    await _check_for_deductions_and_proceed(message, state)


@router.callback_query(ReadingEntry.enter_adjustment, F.data.startswith("adj:"))
async def handle_adjustment_button(query: CallbackQuery, state: FSMContext) -> None:
    """Handles adjustment selection from a button."""
    if not isinstance(query.message, Message) or not query.data:
        return
    try:
        value = Decimal(query.data.split(":", 1)[1])
    except (InvalidOperation, IndexError):
        return
    await query.message.delete()
    await _show_confirmation(query.message, state, value)


@router.message(ReadingEntry.enter_adjustment)
async def handle_adjustment_message(message: Message, state: FSMContext) -> None:
    """Handles manual adjustment entry."""
    if not message.text:
        return
    try:
        value = Decimal(message.text)
    except InvalidOperation:
        await message.answer("Неверный формат. Пожалуйста, введите число.")
        return
    await _show_confirmation(message, state, value)


@router.callback_query(ReadingEntry.confirm_entry, F.data == "confirm")
async def handle_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    """Saves the entered reading to the database."""
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

    # Save current reading with adjustment
    manual_adjustment = Decimal(data.get("manual_adjustment", "0"))
    _, created = await repo.update_or_create(
        defaults={
            "value": data["current_value"],
            "manual_adjustment": manual_adjustment,
        },
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
async def handle_cancellation(query: CallbackQuery, state: FSMContext) -> None:
    """Cancels the reading entry process."""
    await state.clear()
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text("Ввод показаний отменен.")
