from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from tabulate import tabulate

from app.bots.tg.handlers.utils import get_period_keyboard
from app.bots.tg.keyboards.inline import SelectPeriodCallback
from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingError, BillingService

router = Router(name=__name__)


@router.message(F.text == "/summary")
async def handle_summary_command(message: Message):
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
):
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

    # Prepare data
    rows: list[tuple[str, Decimal]] = []

    await query.message.edit_text(f"Формирую отчёт за {period:%B %Y}...")

    for tenant in tenants:
        try:
            invoice, _ = await billing_service.generate_invoice(tenant.id, period)
            rows.append((tenant.name, invoice.amount))
        except BillingError:
            rows.append((tenant.name, Decimal("0")))
        except Exception as e:  # pragma: no cover
            await query.message.answer(f"Ошибка для {tenant.name}: {e}")

    # Build simple table text
    table_body = tabulate(
        rows,
        headers=["Арендатор", "Сумма, ₽"],
        tablefmt="plain",
    )
    table_text = f"<pre>{table_body}</pre>"

    title = "<b>Сводный отчёт за {:%B %Y}</b>".format(period)
    # Edit the original message to show the final report
    await query.message.edit_text(f"{title}\n{table_text}")

    # TODO: export combined PDF/ZIP при необходимости
