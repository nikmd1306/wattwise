"""Handlers for invoice generation."""

from __future__ import annotations

import tempfile
from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.bots.tg.handlers.utils import get_period_keyboard
from app.bots.tg.keyboards.inline import SelectPeriodCallback
from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingError, BillingService
from app.services.export import ExportService

router = Router(name=__name__)


@router.message(F.text == "📄 Получить счет")
async def handle_invoice_command(message: Message):
    """Starts the invoice generation process by showing recent months."""
    builder = get_period_keyboard("invoice")
    await message.answer(
        "Выберите период для выставления счетов:", reply_markup=builder.as_markup()
    )


@router.callback_query(SelectPeriodCallback.filter(F.action == "invoice"))
async def handle_period_for_invoice(
    query: CallbackQuery,
    callback_data: SelectPeriodCallback,
    billing_service: BillingService,
):
    """
    Generates invoices for all tenants for a specified month.
    """
    if not isinstance(query.message, Message):
        return

    await query.answer()

    try:
        period = datetime.strptime(callback_data.period, "%Y-%m").date()
    except ValueError:
        await query.message.edit_text("Неверный формат даты.")
        return

    tenants = await TenantRepository().all()
    if not tenants:
        await query.message.edit_text("Арендаторы не найдены.")
        return

    # Acknowledge the start of the process
    await query.message.edit_text(
        f"Начинаю генерацию счетов за {period:%B %Y} "
        f"для {len(tenants)} арендаторов..."
    )

    export_service = ExportService()
    for tenant in tenants:
        # Check completeness first
        issues = await billing_service.completeness_check(tenant.id, period)
        if issues:
            msg = "\n".join(issues)
            # Use answer on the original message to send new messages
            await query.message.answer(
                f"⚠️ Не могу создать счет для <b>{tenant.name}</b> за "
                f"<b>{period:%B %Y}</b>.\n\n<b>Не хватает данных:</b>\n{msg}"
            )
            continue

        try:
            invoice, details = await billing_service.generate_invoice(tenant.id, period)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                output_path = await export_service.generate_pdf_invoice(
                    invoice, details, temp_file.name
                )
                await query.message.answer_document(
                    FSInputFile(output_path),
                    caption=f"Счет для {tenant.name}",
                )
        except BillingError as e:
            await query.message.answer(
                f"⚠️ Не удалось создать счет для <b>{tenant.name}</b>.\n\n"
                f"<b>Причина:</b> {e}\n\n"
                "<i>Пожалуйста, убедитесь, что все необходимые данные (показания "
                "за предыдущий и текущий месяцы, а также действующий тариф) "
                "введены корректно.</i>"
            )
        except Exception as e:
            await query.message.answer(
                f"❌ Произошла непредвиденная ошибка для {tenant.name}: {e}"
            )
