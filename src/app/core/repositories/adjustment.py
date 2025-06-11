from __future__ import annotations

from app.core.models import Adjustment
from app.core.repositories.base import BaseRepository


class AdjustmentRepository(BaseRepository[Adjustment]):
    """Adjustment-specific repository operations."""

    def __init__(self) -> None:
        super().__init__(Adjustment)
