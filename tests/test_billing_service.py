"""Integration tests for the BillingService."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.models import DeductionLink, Invoice, Meter, Reading, Tariff, Tenant
from app.core.repositories.invoice import InvoiceRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tariff import TariffRepository
from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingService


@pytest.fixture
def billing_service() -> BillingService:
    """Provides a BillingService instance with real repositories."""
    return BillingService(
        tenant_repo=TenantRepository(),
        reading_repo=ReadingRepository(),
        tariff_repo=TariffRepository(),
        invoice_repo=InvoiceRepository(),
    )


@pytest.mark.asyncio
async def test_generate_invoice_simple_case(billing_service: BillingService):
    """
    Tests invoice generation for a simple case: one tenant, one meter,
    using a real in-memory database.
    """
    # --- Arrange ---
    tenant = await Tenant.create(name="Test Tenant")
    meter = await Meter.create(name="Office Meter", tenant=tenant)

    await Reading.create(meter=meter, period=date(2024, 6, 1), value=Decimal("4000"))
    await Reading.create(meter=meter, period=date(2024, 7, 1), value=Decimal("4100"))
    await Tariff.create(
        meter=meter, rate=Decimal("10.5"), period_start=date(2024, 1, 1)
    )

    # --- Act ---
    invoice, _ = await billing_service.generate_invoice(tenant.id, date(2024, 7, 1))

    # --- Assert ---
    assert invoice is not None
    await invoice.fetch_related("tenant")
    assert invoice.tenant.id == tenant.id
    assert invoice.amount == Decimal("1050.00")  # 100 * 10.5

    db_invoice = await Invoice.get(id=invoice.id)
    assert db_invoice is not None
    assert db_invoice.amount == Decimal("1050.00")


@pytest.mark.asyncio
async def test_generate_invoice_with_manual_adjustment(billing_service: BillingService):
    """
    Tests invoice generation for a case with manual adjustment (deduction link).
    """
    # --- Arrange ---
    tenant_a = await Tenant.create(name="Landlord")
    tenant_b = await Tenant.create(name="Sub-tenant")

    parent_meter = await Meter.create(name="Main Building", tenant=tenant_a)
    child_meter = await Meter.create(name="Sub-let Office", tenant=tenant_b)

    # This link is for the UI logic, but we create it for test completeness
    await DeductionLink.create(
        parent_meter=parent_meter,
        child_meter=child_meter,
        description="Sub-let deduction",
    )

    # Parent Meter Data
    await Reading.create(meter=parent_meter, period=date(2024, 6, 1), value=2000)
    await Reading.create(
        meter=parent_meter,
        period=date(2024, 7, 1),
        value=2155,
        manual_adjustment=Decimal("100"),
    )
    await Tariff.create(
        meter=parent_meter, rate=Decimal("40.0"), period_start=date(2024, 1, 1)
    )

    # Child Meter Data
    await Reading.create(meter=child_meter, period=date(2024, 6, 1), value=4000)
    await Reading.create(meter=child_meter, period=date(2024, 7, 1), value=4100)
    await Tariff.create(
        meter=child_meter, rate=Decimal("10.5"), period_start=date(2024, 1, 1)
    )

    # --- Act ---
    invoice_a, _ = await billing_service.generate_invoice(tenant_a.id, date(2024, 7, 1))
    invoice_b, _ = await billing_service.generate_invoice(tenant_b.id, date(2024, 7, 1))

    # --- Assert ---
    # Parent consumption: (2155 - 2000) - 100 = 55. Cost: 55 * 40.0 = 2200
    assert invoice_a.amount == Decimal("2200.00")

    # Child consumption: 4100 - 4000 = 100. Cost: 100 * 10.5 = 1050
    assert invoice_b.amount == Decimal("1050.00")
