"""Base repository for common CRUD operations."""

from __future__ import annotations

from typing import Generic, Type, TypeVar
from uuid import UUID

from tortoise.models import Model

ModelType = TypeVar("ModelType", bound=Model)


class BaseRepository(Generic[ModelType]):
    """Generic repository with basic CRUD methods."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, pk: UUID) -> ModelType | None:
        """Get a model instance by its primary key."""
        return await self.model.get_or_none(id=pk)

    async def get_or_create(
        self, defaults: dict | None = None, **kwargs
    ) -> tuple[ModelType, bool]:
        """Get or create a model instance."""
        return await self.model.get_or_create(defaults=defaults, **kwargs)

    async def all(self) -> list[ModelType]:
        """Get all model instances."""
        return await self.model.all()

    async def create(self, **kwargs) -> ModelType:
        """Create a new model instance."""
        return await self.model.create(**kwargs)

    async def delete(self, pk: UUID) -> int:
        """Delete a model instance by its primary key."""
        instance = await self.get(pk=pk)
        if instance:
            await instance.delete()
            return 1
        return 0
