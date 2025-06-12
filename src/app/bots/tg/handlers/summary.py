from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.bots.tg.handlers.utils import get_period_keyboard
from app.bots.tg.keyboards.inline import SelectPeriodCallback
from app.core.dates import format_period_for_display
from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingError, BillingService
from app.services.export import ExportService

router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.message(F.text == "📊 Сводный отчет")
async def handle_summary_command(message: Message) -> None:
    """Starts the summary report generation by showing recent months."""
    builder = get_period_keyboard("summary")
    await message.answer(
        "Выберите период для формирования отчёта:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(SelectPeriodCallback.filter(F.action == "summary"))
async def handle_summary_period(
    query: CallbackQuery,
    callback_data: SelectPeriodCallback,
    billing_service: BillingService,
) -> None:
    """Generates summary report for all tenants for the given period."""
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

    summary_data: list[dict[str, Any]] = []
    text_rows: list[tuple[str, str]] = []
    grand_total = Decimal("0")

    period_str_display = format_period_for_display(period)
    await query.message.edit_text(f"Формирую отчёт за {period_str_display}...")

    for tenant in tenants:
        try:
            invoice, details = await billing_service.generate_invoice(tenant.id, period)
            summary_data.append(
                {
                    "tenant_name": tenant.name,
                    "total_amount": invoice.amount,
                    "details": list(details.values()),
                }
            )
            text_rows.append((tenant.name, f"{invoice.amount:.2f} ₽"))
            grand_total += invoice.amount
        except BillingError as e:
            summary_data.append(
                {
                    "tenant_name": tenant.name,
                    "total_amount": Decimal("0"),
                    "details": [],
                    "error": str(e),
                }
            )
            text_rows.append((tenant.name, "Ошибка"))
        except Exception as e:
            logger.error(f"Error generating invoice for {tenant.name}: {e}")
            text_rows.append((tenant.name, "Ошибка"))

    period_str_title = format_period_for_display(period)
    title = f"<b>Сводный отчёт по арендаторам за {period_str_title} г.</b>"

    export_service = ExportService()
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            output_path = await export_service.generate_pdf_summary(
                period=period,
                summary_data=summary_data,
                grand_total=grand_total,
                output_path=temp_file.name,
            )
            await query.message.answer_document(
                FSInputFile(output_path),
                caption=title,
            )
            await query.message.delete()
    except Exception as e:
        logger.error(f"Failed to generate summary PDF: {e}", exc_info=True)
        await query.message.edit_text(f"❌ Не удалось создать PDF отчёт. Ошибка: {e}")
