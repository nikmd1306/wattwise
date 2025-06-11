"""Repository for Meter model."""

from __future__ import annotations

from uuid import UUID

from app.core.models import Meter
from app.core.repositories.base import BaseRepository


class MeterRepository(BaseRepository[Meter]):
    """Meter-specific repository operations."""

    def __init__(self) -> None:
        super().__init__(Meter)

    async def get_for_tenant(self, tenant_id: UUID | str) -> list[Meter]:
        """Get all meters for a specific tenant."""
        return await self.model.filter(tenant_id=tenant_id).all()
