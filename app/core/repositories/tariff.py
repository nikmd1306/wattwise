"""Repository for Tariff model."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from tortoise.expressions import Q

from app.core.models import Tariff
from app.core.repositories.base import BaseRepository


class TariffRepository(BaseRepository[Tariff]):
    """Tariff-specific repository operations."""

    def __init__(self) -> None:
        super().__init__(Tariff)

    async def find_for_date(self, meter_id: UUID, target_date: date) -> Tariff | None:
        """Find the active tariff for a given meter on a specific date."""
        return await self.model.filter(
            Q(meter_id=meter_id),
            Q(period_start__lte=target_date),
            Q(Q(period_end__gte=target_date) | Q(period_end__isnull=True)),
        ).first()
