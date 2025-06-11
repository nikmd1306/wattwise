"""Service for scheduling background jobs."""

from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.repositories.tenant import TenantRepository
from app.services.billing import BillingService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled tasks for the application."""

    def __init__(
        self,
        billing_service: BillingService,
        tenant_repo: TenantRepository,
        scheduler: AsyncIOScheduler,
    ):
        self._billing_service = billing_service
        self._tenant_repo = tenant_repo
        self._scheduler = scheduler

    def start(self):
        """Starts the scheduler and adds jobs."""
        logger.info("Starting scheduler...")
        self._scheduler.add_job(
            self._run_nightly_billing,
            trigger=CronTrigger(hour=2, minute=0),  # Run every day at 2:00 AM
            id="nightly_billing",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Scheduler started.")

    async def _run_nightly_billing(self):
        """
        Fetches all tenants and triggers invoice generation for the current day.
        """
        logger.info("Starting nightly billing job.")
        tenants = await self._tenant_repo.all()
        period_date = date.today()

        for tenant in tenants:
            try:
                logger.info(f"Generating invoice for tenant {tenant.name}...")
                await self._billing_service.generate_invoice(tenant.id, period_date)
            except Exception as e:
                logger.error(
                    f"Failed to generate invoice for tenant {tenant.id}: {e}",
                    exc_info=True,
                )
        logger.info("Nightly billing job finished.")
