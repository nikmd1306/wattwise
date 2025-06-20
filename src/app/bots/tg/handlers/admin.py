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
async def handle_new_tenant(message: Message, state: FSMContext) -> None:
    """Starts the process of creating a new tenant."""
    await state.set_state(TenantManagement.enter_name)
    await message.answer("Введите имя нового арендатора:")


@router.message(TenantManagement.enter_name)
async def handle_tenant_name(message: Message, state: FSMContext) -> None:
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
async def handle_new_meter(message: Message, state: FSMContext) -> None:
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
) -> None:
    """Handles tenant selection for meter and asks for its name."""
    if not isinstance(query.message, Message):
        return
    await state.update_data(tenant_id=callback_data.entity_id)
    await state.set_state(MeterManagement.enter_name)
    await query.message.edit_text(
        "Введите название для нового счетчика (например, 'Офис 1'):"
    )


@router.message(MeterManagement.enter_name)
async def handle_meter_name(message: Message, state: FSMContext) -> None:
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

    # Save the entered name and ask if it's a submeter
    await state.update_data(meter_name=meter_name)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Нет", callback_data="sub_no"),
        InlineKeyboardButton(text="Да", callback_data="sub_yes"),
    )
    await message.answer(
        "Назначить этот счётчик под-счётчиком другого?",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(MeterManagement.ask_is_submeter)


@router.callback_query(MeterManagement.ask_is_submeter, F.data == "sub_no")
async def handle_meter_no_sub(query: CallbackQuery, state: FSMContext) -> None:
    """Creates meter without parent."""
    if not isinstance(query.message, Message):
        return
    data = await state.get_data()
    meter = await Meter.create(tenant_id=data["tenant_id"], name=data["meter_name"])
    await query.message.edit_text(f"✅ Счётчик '{meter.name}' успешно добавлен.")
    await state.clear()


@router.callback_query(MeterManagement.ask_is_submeter, F.data == "sub_yes")
async def handle_meter_yes_sub(query: CallbackQuery, state: FSMContext) -> None:
    """Shows list of potential parent meters."""
    if not isinstance(query.message, Message):
        return
    data = await state.get_data()
    tenant_id = data["tenant_id"]
    meters = await MeterRepository().get_for_tenant(UUID(tenant_id))
    if not meters:
        await query.message.edit_text("У арендатора пока нет других счётчиков.")
        await state.clear()
        return
    builder = InlineKeyboardBuilder()
    for meter in meters:
        builder.row(
            InlineKeyboardButton(
                text=meter.name,
                callback_data=f"select_parent:{meter.id}",
            )
        )
    await query.message.edit_text(
        "Выберите родительский счётчик:", reply_markup=builder.as_markup()
    )
    await state.set_state(MeterManagement.select_parent_meter)


@router.callback_query(MeterManagement.select_parent_meter)
async def handle_parent_selected(query: CallbackQuery, state: FSMContext) -> None:
    """Creates new meter with chosen parent."""
    if not isinstance(query.message, Message):
        return
    if not query.data or not query.data.startswith("select_parent:"):
        return
    parent_id = query.data.split(":", 1)[1]
    data = await state.get_data()

    # Get the parent meter for display name
    parent_meter = await Meter.get(id=parent_id)
    meter = await Meter.create(
        tenant_id=data["tenant_id"],
        name=data["meter_name"],
        subtract_from_id=parent_id,
    )
    await query.message.edit_text(
        f"✅ Счётчик '{meter.name}' добавлен как под-счётчик '{parent_meter.name}'."
    )
    await state.clear()


# --- Tariff Creation FSM ---
@router.message(F.text == "📈 Создать тариф")
async def handle_new_tariff(message: Message, state: FSMContext) -> None:
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
) -> None:
    """Handles tenant selection for tariff and shows their meters."""
    if not isinstance(query.message, Message):
        return

    tenant = await TenantRepository().get(pk=UUID(callback_data.entity_id))
    if not tenant:
        return
    await state.update_data(tenant_name=tenant.name)

    meters = await MeterRepository().get_for_tenant(UUID(callback_data.entity_id))
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
) -> None:
    """Handles meter selection and shows available tariff templates."""
    if not isinstance(query.message, Message):
        return

    meter = await Meter.get_or_none(id=callback_data.entity_id)
    if not meter:
        return

    await state.update_data(meter_id=callback_data.entity_id, meter_name=meter.name)

    # Find unique tariff types (name, rate) to offer as templates
    all_tariffs = await Tariff.all().distinct()
    templates: dict[tuple[str, Decimal], Tariff] = {}
    for t in all_tariffs:
        key = (t.name, t.rate)
        if key not in templates:
            templates[key] = t

    text_lines = [
        "<b>Управление тарифами для счётчика:</b>",
        f"«{meter.name}»\n",
        "Выберите шаблон для быстрого назначения или создайте новый.",
    ]
    builder = InlineKeyboardBuilder()

    for template in templates.values():
        builder.row(
            InlineKeyboardButton(
                text=f"↩️ Копировать «{template.name}» ({template.rate:.2f} ₽)",
                callback_data=f"copytar:{template.id}",
            )
        )

    builder.row(
        InlineKeyboardButton(text="➕ Создать новый тип тарифа", callback_data="newtar")
    )

    await query.message.edit_text(
        "\n".join(text_lines), reply_markup=builder.as_markup()
    )
    await state.set_state(TariffManagement.manage_existing)


# --- Tariff: rate name entry (free text) ---
@router.message(TariffManagement.enter_name)
async def handle_tariff_rate_name(message: Message, state: FSMContext) -> None:
    """Stores rate name then asks for numeric rate."""
    if not message.text:
        await message.answer("Название не может быть пустым. Попробуйте еще раз.")
        return

    await state.update_data(name=message.text)
    await state.set_state(TariffManagement.enter_rate)
    await message.answer("Шаг 3/4: Введите <b>ставку тарифа</b> (например, 10.5):")


@router.message(TariffManagement.enter_rate)
async def handle_tariff_rate(message: Message, state: FSMContext) -> None:
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
    await message.answer(
        "Шаг 4/4: Введите дату начала действия тарифа в формате <b>ДД-ММ-ГГГГ</b>:"
    )


@router.message(TariffManagement.enter_start_date)
async def handle_tariff_start_date(message: Message, state: FSMContext) -> None:
    """Handles the start date, asks for confirmation."""
    if not message.text:
        return
    try:
        start_date = datetime.strptime(message.text, "%d-%m-%Y").date()
    except ValueError:
        await message.answer("Неверный формат даты. Введите ДД-ММ-ГГГГ.")
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
        f"<b>Тариф:</b> {data['name']} — {Decimal(data['rate']):.2f} ₽\n"
        f"<b>Действует с:</b> {start_date.strftime('%d.%m.%Y')}\n\n"
        "Все верно?"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, создать", callback_data="confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(TariffManagement.confirm_creation)


@router.callback_query(TariffManagement.confirm_creation, F.data == "confirm")
async def handle_tariff_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    """Handles confirmation, deactivates old tariff, and creates the new one."""
    if not isinstance(query.message, Message):
        return

    data = await state.get_data()
    new_rate = Decimal(data["rate"])
    new_start_date = datetime.fromisoformat(data["start_date"]).date()

    # Find and close the currently active tariff for this meter
    active_tariff = await Tariff.filter(
        meter_id=data["meter_id"], period_end__isnull=True
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
        meter_id=data["meter_id"],
        rate=new_rate,
        period_start=new_start_date,
        name=data["name"],
    )

    await query.message.edit_text(
        "✅ Тариф успешно создан! Старый тариф (если был) автоматически закрыт."
    )
    await state.clear()


@router.callback_query(TariffManagement.confirm_creation, F.data == "cancel")
async def handle_tariff_cancellation(query: CallbackQuery, state: FSMContext) -> None:
    """Handles cancellation of tariff creation."""
    if not isinstance(query.message, Message):
        return
    await query.message.edit_text("Действие отменено.")
    await state.clear()


# --- Tariff management actions ---


@router.callback_query(TariffManagement.manage_existing, F.data == "newtar")
async def handle_new_tariff_action(query: CallbackQuery, state: FSMContext) -> None:
    """Starts creation of a completely new tariff."""
    if not isinstance(query.message, Message):
        return

    await query.message.edit_text(
        "Шаг 2/4: Введите <b>название тарифа</b> (например, 'Ночной'):",
    )
    await state.set_state(TariffManagement.enter_name)


@router.callback_query(TariffManagement.manage_existing, F.data.startswith("copytar:"))
async def handle_copy_tariff(query: CallbackQuery, state: FSMContext) -> None:
    """Copies selected tariff and asks only for new start date."""
    if not isinstance(query.message, Message) or not query.data:
        return

    tariff_id = query.data.split(":", 1)[1]
    tariff = await Tariff.get_or_none(id=tariff_id)
    if not tariff:
        await query.answer("Тариф не найден.", show_alert=True)
        return

    # Pre-fill data and jump straight to start date step
    await state.update_data(name=tariff.name, rate=str(tariff.rate))
    await state.set_state(TariffManagement.enter_start_date)

    await query.message.edit_text(
        "Скопирован тариф «{} — {:.2f} ₽».\n"
        "Введите новую дату начала в формате <b>ДД-ММ-ГГГГ</b>:".format(
            tariff.name, tariff.rate
        )
    )


# --- Meter list / edit ---


@router.message(F.text == "📟 Счётчики")
async def handle_meters_list(message: Message, state: FSMContext) -> None:
    """Shows a list of tenants to choose from for viewing meters."""
    await state.clear()
    tenants = await TenantRepository().all()
    if not tenants:
        await message.answer("Сначала добавьте хотя бы одного арендатора.")
        return

    builder = InlineKeyboardBuilder()
    for tenant in tenants:
        builder.row(
            InlineKeyboardButton(
                text=tenant.name,
                callback_data=f"ml_tenant:{tenant.id}",
            )
        )
    await message.answer(
        "Выберите арендатора для просмотра его счётчиков:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("ml_tenant:"))
async def handle_meter_list_for_tenant(query: CallbackQuery, state: FSMContext) -> None:
    """Shows a list of meters for the selected tenant."""
    if not isinstance(query.message, Message) or not query.data:
        return

    tenant_id = query.data.split(":", 1)[1]
    tenant = await TenantRepository().get(pk=UUID(tenant_id))
    if not tenant:
        return

    meters = await MeterRepository().get_for_tenant(UUID(tenant_id))
    if not meters:
        await query.message.edit_text("У этого арендатора нет счётчиков.")
        return

    text_lines = [f"<b>Счётчики для {tenant.name}:</b>"]
    builder = InlineKeyboardBuilder()

    for m in meters:
        text_lines.append(f"• {m.name}")

        builder.row(
            InlineKeyboardButton(
                text="⚙ Изменить",
                callback_data=f"meter_edit:{m.id}",
            ),
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"meter_del:{m.id}",
            ),
        )

    await query.message.edit_text(
        "\n".join(text_lines), reply_markup=builder.as_markup()
    )


# --- Delete meter ---


@router.callback_query(F.data.startswith("meter_del:"))
async def handle_meter_delete(query: CallbackQuery) -> None:
    """Deletes a meter."""
    if not isinstance(query.message, Message) or not query.data:
        return

    meter_id = query.data.split(":", 1)[1]
    meter = await Meter.get_or_none(id=meter_id)
    if not meter:
        await query.answer("Не найдено.", show_alert=True)
        return

    await meter.delete()
    await query.message.edit_text(f"✅ Счётчик '{meter.name}' удалён.")


# --- Simple parent edit ---


@router.callback_query(F.data.startswith("meter_edit:"))
async def handle_meter_edit(query: CallbackQuery, state: FSMContext) -> None:
    """Shows editing options for a specific meter."""
    if not isinstance(query.message, Message) or not query.data:
        return

    meter_id = query.data.split(":", 1)[1]
    meter = await Meter.get_or_none(id=meter_id)
    if not meter:
        await query.answer("Не найдено.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    # Quick tariff change
    builder.row(
        InlineKeyboardButton(
            text="💱 Новый тариф с сегодня",
            callback_data=f"quick_tariff:{meter.id}",
        )
    )

    await query.message.edit_text(
        f"⚙ Изменение счётчика «{meter.name}». Выберите действие:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("quick_tariff:"))
async def handle_quick_tariff(query: CallbackQuery, state: FSMContext) -> None:
    """Starts the tariff creation FSM with the meter pre-selected."""
    if not isinstance(query.message, Message) or not query.data:
        return

    meter_id = query.data.split(":", 1)[1]
    meter = await Meter.get_or_none(id=meter_id)
    if not meter:
        await query.answer("Счётчик не найден.", show_alert=True)
        return

    tenant = await TenantRepository().get(pk=meter.tenant.id)
    if not tenant:
        return

    # Pre-populate FSM data and jump to rate name entry
    await state.update_data(
        tenant_name=tenant.name,
        meter_id=str(meter.id),
        meter_name=meter.name,
    )

    await state.set_state(TariffManagement.manage_existing)
    await handle_tariff_meter_select(
        query,
        AdminActionCallback(action="smt", entity_id=str(meter.id)),
        state,
    )
