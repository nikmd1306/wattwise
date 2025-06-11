"""Service responsible for generating invoices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import NewType
from uuid import UUID

from dateutil.relativedelta import relativedelta

from app.core import calculations
from app.core.calculations import (
    recalculate_consumption_after_subtraction as _recalc_after_sub,
)
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
    consumption: Consumption
    cost: Decimal


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
        handles subtractive meters, calculates the total cost, and creates
        or updates an invoice record in the database.

        Returns:
            A tuple containing the Invoice object and a dictionary with detailed
            billing results per meter, keyed by meter ID.
        """
        tenant = await self._tenant_repo.get(pk=tenant_id)
        if not tenant:
            raise BillingError(f"Tenant with id {tenant_id} not found.")

        await tenant.fetch_related("meters__subtract_from")

        billing_results: dict[UUID, MeterBillingResult] = {}
        # First, calculate billing for all meters independently
        for meter in tenant.meters:
            result = await self._bill_meter(meter, period_date)
            billing_results[meter.id] = result

        # Then, adjust for subtractive meters
        total_cost = self._adjust_for_subtraction(billing_results)

        # Finally, create or update the invoice
        invoice, _ = await self._invoice_repo.update_or_create(
            defaults={"amount": total_cost},
            tenant_id=tenant.id,
            period=period_date.replace(day=1),
        )
        return invoice, billing_results

    def _adjust_for_subtraction(
        self, billing_results: dict[UUID, MeterBillingResult]
    ) -> Decimal:
        """Adjusts costs for meters that subtract from others."""
        final_costs: dict[UUID, Decimal] = {}

        # Start with original results
        for res in billing_results.values():
            final_costs[res.meter.id] = res.cost

        # Iterate over sub-meters and modify parent results
        sub_meters = [r for r in billing_results.values() if r.meter.subtract_from]
        for sub_result in sub_meters:
            parent_meter = sub_result.meter.subtract_from
            assert parent_meter is not None
            parent_id = parent_meter.id
            parent_result = billing_results[parent_id]

            # Recalculate remaining consumption of parent meter
            try:
                new_parent_consumption = _recalc_after_sub(
                    parent_result.consumption,
                    sub_result.consumption,
                )
            except ValueError as e:
                raise BillingError(str(e)) from e

            # Calculate the cost of the remaining consumption
            parent_rate = parent_result.tariff.rate
            new_parent_cost = calculations.calculate_cost(
                consumption=new_parent_consumption, rate=parent_rate
            )

            # Update the final costs
            deduction = parent_result.cost - new_parent_cost
            final_costs[parent_id] -= deduction

            # Update the billing_results for further use (PDF, API)
            billing_results[parent_id] = MeterBillingResult(
                meter=parent_result.meter,
                tariff=parent_result.tariff,
                consumption=Consumption(new_parent_consumption),
                cost=new_parent_cost,
            )

        return sum(final_costs.values(), Decimal("0"))

    async def _bill_meter(self, meter: Meter, period_date: date) -> MeterBillingResult:
        """Calculates consumption and cost for a single meter."""
        prev_period_date = period_date - relativedelta(months=1)

        current_reading = await self._reading_repo.get_for_period(
            meter.id, period_date, period_date
        )
        prev_reading = await self._reading_repo.get_for_period(
            meter.id, prev_period_date, prev_period_date
        )

        if not current_reading:
            raise BillingError(
                f"No reading for meter {meter.id} in {period_date:%Y-%m}"
            )
        if not prev_reading:
            raise BillingError(
                f"No previous reading for meter {meter.id} in {prev_period_date:%Y-%m}"
            )

        tariff = await self._tariff_repo.find_for_date(meter.id, period_date)
        if not tariff:
            raise BillingError(
                f"No active tariff for meter {meter.id} on {period_date}"
            )

        consumption = calculations.calculate_consumption(
            current_reading=current_reading[0].value,
            previous_reading=prev_reading[0].value,
        )
        cost = calculations.calculate_cost(consumption=consumption, rate=tariff.rate)

        return MeterBillingResult(
            meter=meter, tariff=tariff, consumption=Consumption(consumption), cost=cost
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
        """Sums costs grouped by ``tariff.rate_type``."""
        totals: dict[str, Decimal] = {}
        for res in billing_results.values():
            key = res.tariff.rate_type or "default"
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

        for meter in tenant.meters:
            # Check readings
            curr_reading = await self._reading_repo.get_for_period(
                meter.id, period_date, period_date
            )
            if not curr_reading:
                issues.append(
                    f"Нет показания {period_date:%Y-%m} для счётчика «{meter.name}»."
                )

            prev_reading = await self._reading_repo.get_for_period(
                meter.id, prev_period, prev_period
            )
            if not prev_reading:
                issues.append(f"Нет показания {prev_period:%Y-%m} для «{meter.name}».")

            # Check tariff
            tariff = await self._tariff_repo.find_for_date(meter.id, period_date)
            if not tariff:
                issues.append(
                    f"Нет активного тарифа на {period_date:%Y-%m} для «{meter.name}»."
                )

        return issues
