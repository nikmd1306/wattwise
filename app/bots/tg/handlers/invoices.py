"""Handlers for invoice generation."""

from __future__ import annotations

import tempfile
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message

from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingService
from app.services.export import ExportService

router = Router(name=__name__)


@router.message(Command("invoice"))
async def handle_invoice_command(
    message: Message, command: CommandObject, billing_service: BillingService
):
    """
    Generates invoices for all tenants for a specified month.
    Usage: /invoice YYYY-MM
    """
    if not command.args:
        await message.answer(
            "Пожалуйста, укажите месяц в формате: <code>/invoice ГГГГ-ММ</code>"
        )
        return

    try:
        period = datetime.strptime(command.args, "%Y-%m").date()
    except ValueError:
        await message.answer(
            "Неверный формат даты. Используйте: <code>/invoice ГГГГ-ММ</code>"
        )
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
        except Exception as e:
            await message.answer(f"Ошибка при создании счета для {tenant.name}: {e}")
