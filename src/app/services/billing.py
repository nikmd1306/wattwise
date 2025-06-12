"""Service responsible for generating invoices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import NewType
from uuid import UUID

from dateutil.relativedelta import relativedelta

from app.core import calculations
from app.core.models import Invoice, Meter, Tariff
from app.core.repositories.invoice import InvoiceRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tariff import TariffRepository
from app.core.repositories.tenant import TenantRepository

Consumption = NewType("Consumption", Decimal)


class BillingError(Exception):
    """Custom exception for billing errors."""


@dataclass(frozen=True)
class MeterBillingResult:
    """Represents the calculation result for a single meter."""

    meter: Meter
    tariff: Tariff
    consumption: Consumption  # Final consumption after adjustments
    cost: Decimal
    raw_consumption: Consumption  # Consumption before any adjustments
    manual_adjustment: Decimal  # The value of the adjustment made


class BillingService:
    """Orchestrates the invoice generation process."""

    def __init__(
        self,
        tenant_repo: TenantRepository,
        reading_repo: ReadingRepository,
        tariff_repo: TariffRepository,
        invoice_repo: InvoiceRepository,
    ):
        self._tenant_repo = tenant_repo
        self._reading_repo = reading_repo
        self._tariff_repo = tariff_repo
        self._invoice_repo = invoice_repo

    async def generate_invoice(
        self, tenant_id: UUID, period_date: date
    ) -> tuple[Invoice, dict[UUID, MeterBillingResult]]:
        """
        Generates or updates a consolidated invoice for a given tenant and period.

        This method calculates consumption for all of the tenant's meters,
        applies any manual adjustments, calculates the total cost, and creates
        or updates an invoice record in the database.

        Returns:
            A tuple containing the Invoice object and a dictionary with detailed
            billing results per meter, keyed by meter ID.
        """
        tenant = await self._tenant_repo.get(pk=tenant_id)
        if not tenant:
            raise BillingError(f"Tenant with id {tenant_id} not found.")

        await tenant.fetch_related("meters")

        billing_results: dict[UUID, MeterBillingResult] = {}
        total_cost = Decimal("0")

        # First, calculate billing for all meters independently
        for meter in tenant.meters:
            result = await self._bill_meter(meter, period_date)
            billing_results[meter.id] = result
            total_cost += result.cost

        # Finally, create or update the invoice
        invoice, _ = await self._invoice_repo.update_or_create(
            defaults={"amount": total_cost},
            tenant_id=tenant.id,
            period=period_date.replace(day=1),
        )
        return invoice, billing_results

    async def _bill_meter(self, meter: Meter, period_date: date) -> MeterBillingResult:
        """Calculates consumption and cost for a single meter."""
        prev_period_date = period_date - relativedelta(months=1)

        current_readings = await self._reading_repo.get_for_period(
            meter.id, period_date, period_date
        )
        prev_readings = await self._reading_repo.get_for_period(
            meter.id, prev_period_date, prev_period_date
        )

        if not current_readings:
            raise BillingError(
                f"No reading for meter {meter.id} in {period_date:%Y-%m}"
            )
        if not prev_readings:
            raise BillingError(
                f"No previous reading for meter {meter.id} in {prev_period_date:%Y-%m}"
            )

        current_reading = current_readings[0]
        prev_reading = prev_readings[0]

        tariff = await self._tariff_repo.find_for_date(meter.id, period_date)
        if not tariff:
            raise BillingError(
                f"No active tariff for meter {meter.id} on {period_date}"
            )

        consumption = calculations.calculate_consumption(
            current_reading=current_reading.value,
            previous_reading=prev_reading.value,
            adjustment=current_reading.manual_adjustment or Decimal("0"),
        )
        raw_consumption = calculations.calculate_consumption(
            current_reading=current_reading.value, previous_reading=prev_reading.value
        )

        if consumption < 0:
            consumption = Decimal("0")

        cost = calculations.calculate_cost(consumption=consumption, rate=tariff.rate)

        return MeterBillingResult(
            meter=meter,
            tariff=tariff,
            consumption=Consumption(consumption),
            cost=cost,
            raw_consumption=Consumption(raw_consumption),
            manual_adjustment=current_reading.manual_adjustment or Decimal("0"),
        )

    async def add_adjustment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        description: str,
    ) -> None:
        """Adds a manual adjustment to an invoice and updates its amount.

        Args:
            invoice_id: Target invoice ID.
            amount: Positive or negative monetary value.
            description: Short explanation shown to users.
        """
        # Lazy import to avoid circular deps
        from app.core.repositories.adjustment import AdjustmentRepository

        invoice = await self._invoice_repo.get(pk=invoice_id)
        if not invoice:
            raise BillingError(f"Invoice {invoice_id} not found.")

        # Create the adjustment record
        adj_repo = AdjustmentRepository()
        await adj_repo.create(
            invoice_id=invoice_id, amount=amount, description=description
        )

        # Update invoice total
        invoice.amount += amount
        await invoice.save()

    async def list_adjustments(self, invoice_id: UUID):
        """Returns all adjustments for a given invoice."""
        invoice = await self._invoice_repo.get(pk=invoice_id)
        if not invoice:
            raise BillingError(f"Invoice {invoice_id} not found.")
        await invoice.fetch_related("adjustments")
        return list(invoice.adjustments)

    @staticmethod
    def aggregate_costs_by_rate_type(
        billing_results: dict[UUID, "MeterBillingResult"],
    ) -> dict[str, Decimal]:
        """Sums costs grouped by ``tariff.name``."""
        totals: dict[str, Decimal] = {}
        for res in billing_results.values():
            key = res.tariff.name or "default"
            totals[key] = totals.get(key, Decimal("0")) + res.cost
        return totals

    async def completeness_check(self, tenant_id: UUID, period_date: date) -> list[str]:
        """Returns human-readable list of missing data for given tenant/period.

        Checks:
        1. Есть ли показания за текущий период.
        2. Есть ли показания за предыдущий период.
        3. Активный тариф на дату period_date.
        """

        tenant = await self._tenant_repo.get(pk=tenant_id)
        if not tenant:
            return [f"Арендатор {tenant_id} не найден."]

        await tenant.fetch_related("meters")

        issues: list[str] = []
        prev_period = period_date - relativedelta(months=1)

        # Using Russian month names
        current_month_str = period_date.strftime("%B %Y").capitalize()
        prev_month_str = prev_period.strftime("%B %Y").capitalize()

        for meter in tenant.meters:
            meter_issues: list[str] = []
            # Check readings
            curr_reading = await self._reading_repo.get_for_period(
                meter.id, period_date, period_date
            )
            if not curr_reading:
                meter_issues.append(f"  • нет показания за <b>{current_month_str}</b>")

            prev_reading = await self._reading_repo.get_for_period(
                meter.id, prev_period, prev_period
            )
            if not prev_reading:
                meter_issues.append(
                    f"  • нет показания за <b>{prev_month_str}</b> (нужно для расчёта)"
                )

            # Check tariff
            tariff = await self._tariff_repo.find_for_date(meter.id, period_date)
            if not tariff:
                meter_issues.append(
                    f"  • нет активного тарифа на <b>{current_month_str}</b>"
                )

            if meter_issues:
                issues.append(f"<u>Счётчик «{meter.name}»:</u>")
                issues.extend(meter_issues)

        return issues
