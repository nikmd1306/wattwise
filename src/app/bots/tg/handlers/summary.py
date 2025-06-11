from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from tabulate import tabulate

from app.bots.tg.states import SummaryGeneration
from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingError, BillingService

router = Router(name=__name__)


@router.message(F.text == "/summary")
async def handle_summary_command(message: Message, state: FSMContext):
    """Starts the summary report generation by asking for a period."""
    await state.set_state(SummaryGeneration.enter_period)
    await message.answer("Введите период отчёта в формате <b>ГГГГ-ММ</b>:")


@router.message(SummaryGeneration.enter_period)
async def handle_summary_period(
    message: Message, state: FSMContext, billing_service: BillingService
):
    """Generates summary report for all tenants for the given period."""
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

    # Prepare data
    rows: list[tuple[str, Decimal]] = []

    for tenant in tenants:
        try:
            invoice, _ = await billing_service.generate_invoice(tenant.id, period)
            rows.append((tenant.name, invoice.amount))
        except BillingError:
            rows.append((tenant.name, Decimal("0")))
        except Exception as e:  # pragma: no cover
            await message.answer(f"Ошибка для {tenant.name}: {e}")

    # Build simple table text
    table_body = tabulate(
        rows,
        headers=["Арендатор", "Сумма, ₽"],
        tablefmt="plain",
    )
    table_text = f"<pre>{table_body}</pre>"

    title = "<b>Сводный отчёт за {:%B %Y}</b>".format(period)
    await message.answer(f"{title}\n{table_text}")

    # TODO: export combined PDF/ZIP при необходимости
