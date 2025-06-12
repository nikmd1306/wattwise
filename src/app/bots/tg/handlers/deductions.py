"""Handlers for deduction link management."""

from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.tg.keyboards.inline import DeductionLinkCallback
from app.bots.tg.middlewares.access import AdminAccessMiddleware
from app.bots.tg.states import DeductionLinkManagement
from app.core.models import DeductionLink
from app.core.repositories.meter import MeterRepository
from app.core.repositories.tenant import TenantRepository

router = Router(name=__name__)
router.message.middleware(AdminAccessMiddleware())
router.callback_query.middleware(AdminAccessMiddleware())


async def _get_main_view(message: Message | CallbackQuery, state: FSMContext) -> None:
    """Shows the main view with existing links and a create button."""
    await state.clear()
    await state.set_state(DeductionLinkManagement.start)

    links = await DeductionLink.all().prefetch_related(
        "parent_meter__tenant", "child_meter__tenant"
    )

    builder = InlineKeyboardBuilder()
    text_lines = ["<b>🔗 Управление связями для вычетов</b>\n"]

    if not links:
        text_lines.append("Пока не создано ни одной связи.")
    else:
        text_lines.append("Существующие связи:")
        for link in links:
            # Shorten names for display
            parent_info = (
                f"{link.parent_meter.tenant.name[:10]}…: "
                f"{link.parent_meter.name[:10]}…"
            )
            child_info = (
                f"{link.child_meter.tenant.name[:10]}…: "
                f"{link.child_meter.name[:10]}…"
            )
            text_lines.append(f"• Из 📄({parent_info}) вычитается ➡️ ({child_info})")
            builder.row(
                InlineKeyboardButton(
                    text=f"🗑️ Удалить связь «{link.description or 'Без имени'}»",
                    callback_data=DeductionLinkCallback(
                        action="delete", link_id=str(link.id)
                    ).pack(),
                )
            )

    builder.row(
        InlineKeyboardButton(
            text="➕ Создать новую связь",
            callback_data=DeductionLinkCallback(action="create").pack(),
        )
    )

    text = "\n".join(text_lines)
    if isinstance(message, Message):
        await message.answer(text, reply_markup=builder.as_markup())
    elif isinstance(message.message, Message):
        await message.message.edit_text(text, reply_markup=builder.as_markup())


@router.message(F.text == "🔗 Связи для вычетов")
async def handle_deductions_command(message: Message, state: FSMContext) -> None:
    """Entry point for deduction link management."""
    await _get_main_view(message, state)


@router.callback_query(
    DeductionLinkManagement.start, DeductionLinkCallback.filter(F.action == "delete")
)
async def handle_delete_link(
    query: CallbackQuery, callback_data: DeductionLinkCallback, state: FSMContext
) -> None:
    """Deletes a deduction link."""
    if callback_data.link_id:
        await DeductionLink.filter(id=callback_data.link_id).delete()
    await query.answer("Связь удалена.")
    await _get_main_view(query, state)


@router.callback_query(
    DeductionLinkManagement.start, DeductionLinkCallback.filter(F.action == "create")
)
async def handle_create_start(query: CallbackQuery, state: FSMContext) -> None:
    """Starts the creation of a new deduction link by selecting the parent tenant."""
    if not isinstance(query.message, Message):
        return
    await state.set_state(DeductionLinkManagement.select_parent_tenant)
    tenants = await TenantRepository().all()
    builder = InlineKeyboardBuilder()
    for tenant in tenants:
        builder.row(
            InlineKeyboardButton(
                text=tenant.name,
                callback_data=DeductionLinkCallback(
                    action="select_parent_tenant", tenant_id=str(tenant.id)
                ).pack(),
            )
        )
    await query.message.edit_text(
        "<b>Шаг 1/5:</b> Выберите арендатора, со счётчика которого "
        "будут <b>вычитать</b> показания:",
        reply_markup=builder.as_markup(),
    )


async def _select_meter(
    query: CallbackQuery,
    state: FSMContext,
    tenant_id: str,
    next_action: str,
    text: str,
) -> None:
    """Helper to show meters for a tenant."""
    if not isinstance(query.message, Message):
        return
    meters = await MeterRepository().get_for_tenant(tenant_id)
    if not meters:
        await query.message.edit_text("У этого арендатора нет счетчиков.")
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    for meter in meters:
        builder.row(
            InlineKeyboardButton(
                text=meter.name,
                callback_data=DeductionLinkCallback(
                    action=next_action, meter_id=str(meter.id)
                ).pack(),
            )
        )
    await query.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(
    DeductionLinkManagement.select_parent_tenant,
    DeductionLinkCallback.filter(F.action == "select_parent_tenant"),
)
async def handle_parent_tenant_selected(
    query: CallbackQuery, callback_data: DeductionLinkCallback, state: FSMContext
) -> None:
    """Handles parent tenant selection and shows its meters."""
    if not callback_data.tenant_id:
        return
    await state.update_data(parent_tenant_id=callback_data.tenant_id)
    await state.set_state(DeductionLinkManagement.select_parent_meter)
    await _select_meter(
        query,
        state,
        callback_data.tenant_id,
        "select_parent_meter",
        "<b>Шаг 2/5:</b> Выберите счётчик, с которого будут <b>вычитать</b>:",
    )


@router.callback_query(
    DeductionLinkManagement.select_parent_meter,
    DeductionLinkCallback.filter(F.action == "select_parent_meter"),
)
async def handle_parent_meter_selected(
    query: CallbackQuery, callback_data: DeductionLinkCallback, state: FSMContext
) -> None:
    """Handles parent meter selection and asks for child tenant."""
    if not isinstance(query.message, Message):
        return
    if not callback_data.meter_id:
        return
    await state.update_data(parent_meter_id=callback_data.meter_id)
    await state.set_state(DeductionLinkManagement.select_child_tenant)

    tenants = await TenantRepository().all()
    builder = InlineKeyboardBuilder()
    for tenant in tenants:
        builder.row(
            InlineKeyboardButton(
                text=tenant.name,
                callback_data=DeductionLinkCallback(
                    action="select_child_tenant", tenant_id=str(tenant.id)
                ).pack(),
            )
        )
    await query.message.edit_text(
        "<b>Шаг 3/5:</b> Выберите арендатора, счётчик которого "
        "будет <b>источником</b> для вычета:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(
    DeductionLinkManagement.select_child_tenant,
    DeductionLinkCallback.filter(F.action == "select_child_tenant"),
)
async def handle_child_tenant_selected(
    query: CallbackQuery, callback_data: DeductionLinkCallback, state: FSMContext
) -> None:
    """Handles child tenant selection and shows its meters."""
    if not callback_data.tenant_id:
        return
    await state.update_data(child_tenant_id=callback_data.tenant_id)
    await state.set_state(DeductionLinkManagement.select_child_meter)
    await _select_meter(
        query,
        state,
        callback_data.tenant_id,
        "select_child_meter",
        "<b>Шаг 4/5:</b> Выберите счётчик-<b>источник</b>:",
    )


@router.callback_query(
    DeductionLinkManagement.select_child_meter,
    DeductionLinkCallback.filter(F.action == "select_child_meter"),
)
async def handle_child_meter_selected(
    query: CallbackQuery, callback_data: DeductionLinkCallback, state: FSMContext
) -> None:
    """Handles child meter selection and asks for a description."""
    if not isinstance(query.message, Message):
        return
    if not callback_data.meter_id:
        return
    await state.update_data(child_meter_id=callback_data.meter_id)
    await state.set_state(DeductionLinkManagement.enter_description)
    await query.message.edit_text(
        "<b>Шаг 5/5:</b> Введите краткое описание для этой связи, "
        "которое увидит пользователь (например, 'Вычет за склад')."
    )


@router.message(DeductionLinkManagement.enter_description)
async def handle_description(message: Message, state: FSMContext) -> None:
    """Handles description and asks for confirmation."""
    if not message.text:
        await message.answer("Описание не может быть пустым.")
        return

    await state.update_data(description=message.text)
    data = await state.get_data()

    # Fetch details for confirmation text
    repo = MeterRepository()
    parent_meter = await repo.model.get(
        id=UUID(data["parent_meter_id"])
    ).prefetch_related("tenant")
    child_meter = await repo.model.get(
        id=UUID(data["child_meter_id"])
    ).prefetch_related("tenant")

    parent_info = f"«{parent_meter.name}» (Арендатор: {parent_meter.tenant.name})"
    child_info = f"«{child_meter.name}» (Арендатор: {child_meter.tenant.name})"

    text_lines = [
        "<b>Подтвердите создание связи:</b>\n",
        f"🔹 <b>Из счётчика:</b> {parent_info}",
        f"🔸 <b>Вычитается счётчик:</b> {child_info}",
        f"📝 <b>Описание:</b> {data['description']}\n",
        "Эта связь будет использоваться для подсказки пользователю при вводе "
        "показаний. Всё верно?",
    ]
    text = "\n".join(text_lines)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, создать", callback_data="confirm"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(DeductionLinkManagement.confirm_creation)


@router.callback_query(DeductionLinkManagement.confirm_creation, F.data == "confirm")
async def handle_confirmation(query: CallbackQuery, state: FSMContext) -> None:
    """Creates the link and returns to the main view."""
    data = await state.get_data()
    await DeductionLink.create(
        parent_meter_id=data["parent_meter_id"],
        child_meter_id=data["child_meter_id"],
        description=data["description"],
    )
    await query.answer("✅ Связь успешно создана!")
    await _get_main_view(query, state)


@router.callback_query(DeductionLinkManagement.confirm_creation, F.data == "cancel")
async def handle_cancellation(query: CallbackQuery, state: FSMContext) -> None:
    """Cancels creation and returns to the main view."""
    await query.answer("Действие отменено.")
    await _get_main_view(query, state)
