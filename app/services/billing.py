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

    async def generate_invoice(self, tenant_id: UUID, period_date: date) -> Invoice:
        """
        Generates a consolidated invoice for a given tenant and period.

        This method calculates consumption for all of the tenant's meters,
        handles subtractive meters, calculates the total cost, and creates
        an invoice record in the database.
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

        # Finally, create and save the invoice
        invoice = await self._invoice_repo.create(
            tenant=tenant,
            period=period_date.replace(day=1),
            amount=total_cost,
        )
        return invoice

    def _adjust_for_subtraction(
        self, billing_results: dict[UUID, MeterBillingResult]
    ) -> Decimal:
        """Adjusts costs for meters that subtract from others."""
        final_costs = {
            result.meter.id: result.cost for result in billing_results.values()
        }

        for result in billing_results.values():
            if result.meter.subtract_from:
                parent_meter_result = billing_results[result.meter.subtract_from.id]
                parent_tariff = parent_meter_result.tariff

                # The cost to subtract is the sub-meter's
                # CONSUMPTION at the PARENT's rate.
                subtraction_cost = calculations.calculate_cost(
                    consumption=result.consumption,
                    rate=parent_tariff.rate,
                )
                final_costs[parent_meter_result.meter.id] -= subtraction_cost

        # Provide a Decimal start value to keep the return type consistent
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
