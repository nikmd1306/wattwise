"""Handlers for invoice generation."""

from __future__ import annotations

import tempfile
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from app.bots.tg.states import InvoiceGeneration
from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingService, BillingError
from app.services.export import ExportService

router = Router(name=__name__)


@router.message(F.text == "📄 Получить счет")
async def handle_invoice_command(message: Message, state: FSMContext):
    """Starts the invoice generation process by asking for a period."""
    await state.set_state(InvoiceGeneration.enter_period)
    await message.answer(
        "Введите период для выставления счетов в формате <b>ГГГГ-ММ</b>:"
    )


@router.message(InvoiceGeneration.enter_period)
async def handle_period_for_invoice(
    message: Message, state: FSMContext, billing_service: BillingService
):
    """
    Generates invoices for all tenants for a specified month.
    """
    await state.clear()
    if not message.text:
        return

    try:
        period = datetime.strptime(message.text, "%Y-%m").date()
    except ValueError:
        await message.answer("Неверный формат даты. Используйте: <b>ГГГГ-ММ</b>")
        return

    tenants = await TenantRepository().all()
    if not tenants:
        await message.answer("Арендаторы не найдены.")
        return

    await message.answer(
        f"Начинаю генерацию счетов за {period:%B %Y} для {len(tenants)} арендаторов..."
    )

    export_service = ExportService()
    for tenant in tenants:
        try:
            invoice = await billing_service.generate_invoice(tenant.id, period)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                output_path = await export_service.generate_pdf_invoice(
                    invoice, temp_file.name
                )
                await message.answer_document(
                    FSInputFile(output_path),
                    caption=f"Счет для {tenant.name}",
                )
        except BillingError as e:
            await message.answer(
                f"⚠️ Не удалось создать счет для <b>{tenant.name}</b>.\n\n"
                f"<b>Причина:</b> {e}\n\n"
                "<i>Пожалуйста, убедитесь, что все необходимые данные (показания "
                "за предыдущий и текущий месяцы, а также действующий тариф) "
                "введены корректно.</i>"
            )
        except Exception as e:
            await message.answer(
                f"❌ Произошла непредвиденная ошибка для {tenant.name}: {e}"
            )
