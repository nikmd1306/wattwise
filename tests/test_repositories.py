from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.models import Meter, Reading, Tariff, Tenant
from app.core.repositories.meter import MeterRepository
from app.core.repositories.reading import ReadingRepository
from app.core.repositories.tariff import TariffRepository
from app.core.repositories.tenant import TenantRepository
from app.services.scheduler import SchedulerService
from app.services.billing import BillingService
from app.core.repositories.invoice import InvoiceRepository


@pytest.mark.asyncio
async def test_tenant_meter_crud():
    tenant_repo = TenantRepository()
    meter_repo = MeterRepository()

    tenant = await tenant_repo.create(name="ACME")
    meter = await meter_repo.create(name="Main", tenant=tenant)

    fetched = await meter_repo.get(meter.id)
    assert fetched is not None and fetched.id == meter.id

    deleted = await meter_repo.delete(meter.id)
    assert deleted == 1


@pytest.mark.asyncio
async def test_scheduler_runs_job(caplog):
    """Smoke-тест: планировщик вызывает BillingService без ошибок."""

    tenant = await Tenant.create(name="SchedTenant")
    meter = await Meter.create(name="M1", tenant=tenant)
    today = date.today().replace(day=1)
    prev_month = today - relativedelta(months=1)

    await Reading.create(meter=meter, period=prev_month, value=Decimal("0"))
    await Reading.create(meter=meter, period=today, value=Decimal("1"))
    await Tariff.create(
        meter=meter,
        rate=Decimal("1.0"),
        period_start=today.replace(year=today.year - 1),
    )

    billing = BillingService(
        tenant_repo=TenantRepository(),
        reading_repo=ReadingRepository(),
        tariff_repo=TariffRepository(),
        invoice_repo=InvoiceRepository(),
    )

    scheduler = AsyncIOScheduler()
    service = SchedulerService(billing, TenantRepository(), scheduler)

    caplog.set_level("INFO")

    await service._run_nightly_billing()

    assert "Generating invoice" in caplog.text
