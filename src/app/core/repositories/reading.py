"""Repository for Reading model."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.models import Reading
from app.core.repositories.base import BaseRepository


class ReadingRepository(BaseRepository[Reading]):
    """Reading-specific repository operations."""

    def __init__(self) -> None:
        super().__init__(Reading)

    async def get_for_period(
        self, meter_id: UUID, start_date: date, end_date: date
    ) -> list[Reading]:
        """Get readings for a meter within a specific period."""
        return await self.model.filter(
            meter_id=meter_id, period__gte=start_date, period__lte=end_date
        ).order_by("period")
