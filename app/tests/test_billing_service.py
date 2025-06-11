"""Integration tests for the BillingService."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.models import Invoice, Meter, Reading, Tariff, Tenant
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
    invoice = await billing_service.generate_invoice(tenant.id, date(2024, 7, 1))

    # --- Assert ---
    assert invoice is not None
    await invoice.fetch_related("tenant")
    assert invoice.tenant.id == tenant.id
    assert invoice.amount == Decimal("1050.00")  # 100 * 10.5

    db_invoice = await Invoice.get(id=invoice.id)
    assert db_invoice is not None
    assert db_invoice.amount == Decimal("1050.00")


@pytest.mark.asyncio
async def test_generate_invoice_with_subtraction(billing_service: BillingService):
    """Tests invoice generation with a subtractive sub-meter."""
    # --- Arrange ---
    tenant = await Tenant.create(name="StaviLon")
    parent_meter = await Meter.create(name="Main Building", tenant=tenant)
    sub_meter = await Meter.create(
        name="Bondarenko Warehouse", tenant=tenant, subtract_from=parent_meter
    )

    # Parent Meter Data
    await Reading.create(meter=parent_meter, period=date(2024, 6, 1), value=2000)
    await Reading.create(meter=parent_meter, period=date(2024, 7, 1), value=2100)
    await Tariff.create(
        meter=parent_meter, rate=Decimal("40.0"), period_start=date(2024, 1, 1)
    )

    # Sub-Meter Data
    await Reading.create(meter=sub_meter, period=date(2024, 6, 1), value=4000)
    await Reading.create(meter=sub_meter, period=date(2024, 7, 1), value=4100)
    await Tariff.create(
        meter=sub_meter, rate=Decimal("10.5"), period_start=date(2024, 1, 1)
    )

    # Expected:
    # Parent Cost: (2100 - 2000) * 40.0 = 4000
    # Sub Cost: (4100 - 4000) * 10.5 = 1050
    # Subtraction: (4100 - 4000) * 40.0 (Parent's Tariff) = 4000
    # Total = 4000 + 1050 - 4000 = 1050
    expected_amount = Decimal("1050.00")

    # --- Act ---
    invoice = await billing_service.generate_invoice(tenant.id, date(2024, 7, 1))

    # --- Assert ---
    assert invoice.amount == expected_amount
    db_invoice = await Invoice.get(id=invoice.id)
    assert db_invoice.amount == expected_amount
