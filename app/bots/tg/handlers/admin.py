"""Handlers for admin commands."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.tg.middlewares.access import AdminAccessMiddleware
from app.bots.tg.states import TenantManagement, TariffManagement, MeterManagement
from app.core.repositories.tenant import TenantRepository
from app.core.repositories.meter import MeterRepository
from app.core.models import Tariff, Meter
from app.bots.tg.keyboards.inline import AdminActionCallback

router = Router(name=__name__)

router.message.middleware(AdminAccessMiddleware())
router.callback_query.middleware(AdminAccessMiddleware())


# --- Tenant Creation FSM ---
@router.message(F.text == "👤 Создать арендатора")
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


# --- Meter Creation FSM ---
@router.message(F.text == "📟 Добавить счетчик")
async def handle_new_meter(message: Message, state: FSMContext):
    """Starts the FSM for adding a new meter."""
    tenants = await TenantRepository().all()
    if not tenants:
        await message.answer("Сначала добавьте хотя бы одного арендатора.")
        return

    builder = InlineKeyboardBuilder()
    for tenant in tenants:
        builder.row(
            InlineKeyboardButton(
                text=tenant.name,
                callback_data=AdminActionCallback(
                    action="stm", entity_id=str(tenant.id)
                ).pack(),
            )
        )
    await message.answer(
        "Выберите арендатора, которому хотите добавить счетчик:",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(MeterManagement.select_tenant)


@router.callback_query(AdminActionCallback.filter(F.action == "stm"))
async def handle_meter_tenant_select(
    query: CallbackQuery, callback_data: AdminActionCallback, state: FSMContext
):
    """Handles tenant selection for meter and asks for its name."""
    if not isinstance(query.message, Message):
        return
    await state.update_data(tenant_id=callback_data.entity_id)
    await state.set_state(MeterManagement.enter_name)
    await query.message.edit_text(
        "Введите название для нового счетчика (например, 'Офис 1'):"
    )


@router.message(MeterManagement.enter_name)
async def handle_meter_name(message: Message, state: FSMContext):
    """Handles the new meter's name and saves it."""
    if not message.text:
        await message.answer("Название не может быть пустым. Попробуйте еще раз.")
        return

    data = await state.get_data()
    tenant_id = data["tenant_id"]
    meter_name = message.text

    # Check if a meter with this name already exists for the tenant
    existing_meter = await Meter.filter(tenant_id=tenant_id, name=meter_name).first()
    if existing_meter:
        await message.answer(
            f"Счетчик с именем '{meter_name}' у этого арендатора уже существует."
        )
        await state.clear()
        return

    await Meter.create(tenant_id=tenant_id, name=meter_name)
    await message.answer(f"Счетчик '{meter_name}' успешно добавлен.")
    await state.clear()


# --- Tariff Creation FSM ---
@router.message(F.text == "📈 Создать тариф")
async def handle_new_tariff(message: Message, state: FSMContext):
    """Starts the FSM for creating a new tariff by selecting a tenant."""
    tenants = await TenantRepository().all()
    if not tenants:
        await message.answer("Сначала добавьте хотя бы одного арендатора.")
        return

    builder = InlineKeyboardBuilder()
    for tenant in tenants:
        builder.row(
            InlineKeyboardButton(
                text=tenant.name,
                callback_data=AdminActionCallback(
                    action="stt", entity_id=str(tenant.id)
                ).pack(),
            )
        )
    await message.answer(
        "Шаг 1/4: Выберите арендатора, для которого создается тариф:",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(TariffManagement.select_tenant)


@router.callback_query(AdminActionCallback.filter(F.action == "stt"))
async def handle_tariff_tenant_select(
    query: CallbackQuery, callback_data: AdminActionCallback, state: FSMContext
):
    """Handles tenant selection for tariff and shows their meters."""
    if not isinstance(query.message, Message):
        return

    tenant = await TenantRepository().get(pk=UUID(callback_data.entity_id))
    if not tenant:
        return
    await state.update_data(tenant_name=tenant.name)

    meters = await MeterRepository().get_for_tenant(callback_data.entity_id)
    if not meters:
        await query.message.edit_text(
            "У этого арендатора нет счетчиков. Сначала добавьте один."
        )
        return await state.clear()

    builder = InlineKeyboardBuilder()
    for meter in meters:
        builder.row(
            InlineKeyboardButton(
                text=meter.name,
                callback_data=AdminActionCallback(
                    action="smt", entity_id=str(meter.id)
                ).pack(),
            )
        )
    await query.message.edit_text(
        "Шаг 2/4: Выберите счетчик для нового тарифа:",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(TariffManagement.select_meter)


@router.callback_query(
    TariffManagement.select_meter, AdminActionCallback.filter(F.action == "smt")
)
async def handle_tariff_meter_select(
    query: CallbackQuery, callback_data: AdminActionCallback, state: FSMContext
):
    """Handles meter selection and asks for the tariff rate."""
    if not isinstance(query.message, Message):
        return

    meter = await Meter.get_or_none(id=callback_data.entity_id)
    if not meter:
        return
    await state.update_data(meter_id=callback_data.entity_id, meter_name=meter.name)
    await state.set_state(TariffManagement.enter_rate)
    await query.message.edit_text("Шаг 3/4: Введите ставку тарифа (например, 10.5):")


@router.message(TariffManagement.enter_rate)
async def handle_tariff_rate(message: Message, state: FSMContext):
    """Handles the tariff rate and asks for the start date."""
    if not message.text:
        return
    try:
        # We just validate it's a decimal, but store as string to prevent
        # JSON issues with other FSM storages
        Decimal(message.text)
    except InvalidOperation:
        await message.answer("Неверный формат. Введите число.")
        return

    await state.update_data(rate=message.text)
    await state.set_state(TariffManagement.enter_start_date)
    await message.answer("Шаг 4/4: Введите дату начала действия тарифа (ГГГГ-ММ-ДД):")


@router.message(TariffManagement.enter_start_date)
async def handle_tariff_start_date(message: Message, state: FSMContext):
    """Handles the start date, asks for confirmation."""
    if not message.text:
        return
    try:
        start_date = datetime.strptime(message.text, "%Y-%m-%d").date()
    except ValueError:
        await message.answer("Неверный формат даты. Введите ГГГГ-ММ-ДД.")
        return

    if start_date.day != 1:
        await message.answer(
            "❌ **Ошибка:** Тариф должен начинаться с первого дня месяца "
            "(например, 2025-07-01). Пожалуйста, введите дату снова."
        )
        return

    await state.update_data(start_date=start_date.isoformat())
    data = await state.get_data()

    text = (
        "<b>Подтвердите создание тарифа:</b>\n\n"
        f"<b>Арендатор:</b> {data['tenant_name']}\n"
        f"<b>Счетчик:</b> {data['meter_name']}\n"
        f"<b>Ставка:</b> {data['rate']}\n"
        f"<b>Действует с:</b> {start_date.strftime('%d.%m.%Y')}\n\n"
        "Все верно?"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, создать", callback_data="confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(TariffManagement.confirm_creation)


@router.callback_query(TariffManagement.confirm_creation, F.data == "confirm")
async def handle_tariff_confirmation(query: CallbackQuery, state: FSMContext):
    """Handles confirmation, deactivates old tariff, and creates the new one."""
    if not isinstance(query.message, Message):
        return

    data = await state.get_data()
    meter_id = data["meter_id"]
    new_rate = Decimal(data["rate"])
    new_start_date = datetime.fromisoformat(data["start_date"]).date()

    # Find and close the currently active tariff for this meter
    active_tariff = await Tariff.filter(
        meter_id=meter_id, period_end__isnull=True
    ).first()

    if active_tariff:
        if new_start_date <= active_tariff.period_start:
            await query.message.edit_text(
                "❌ Ошибка: Дата начала нового тарифа не может быть раньше или "
                "такой же, как у текущего активного тарифа."
            )
            await state.clear()
            return

        active_tariff.period_end = new_start_date - timedelta(days=1)
        await active_tariff.save()

    # Create the new tariff
    await Tariff.create(
        meter_id=meter_id,
        rate=new_rate,
        period_start=new_start_date,
    )

    await query.message.edit_text(
        "✅ Тариф успешно создан! Старый тариф (если был) автоматически закрыт."
    )
    await state.clear()


@router.callback_query(TariffManagement.confirm_creation, F.data == "cancel")
async def handle_tariff_cancellation(query: CallbackQuery, state: FSMContext):
    """Handles cancellation of tariff creation."""
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text("Действие отменено.")
    await state.clear()
