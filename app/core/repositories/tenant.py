"""Repository for Tenant model."""

from __future__ import annotations

from app.core.models import Tenant
from app.core.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    """Tenant-specific repository operations."""

    def __init__(self) -> None:
        super().__init__(Tenant)

    async def get_by_name(self, name: str) -> Tenant | None:
        """Get a tenant by name."""
        return await self.model.get_or_none(name=name)
