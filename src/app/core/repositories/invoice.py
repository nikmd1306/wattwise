"""Repository for Invoice model."""

from __future__ import annotations

from app.core.models import Invoice
from app.core.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    """Invoice-specific repository operations."""

    def __init__(self) -> None:
        super().__init__(Invoice)
