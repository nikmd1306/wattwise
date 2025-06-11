"""Domain models for the WattWise application."""

from __future__ import annotations

import enum
import uuid

from tortoise import fields, models


class ResourceType(str, enum.Enum):
    """Enum for resource types like electricity, water, etc."""

    ELECTRICITY = "electricity"
    WATER = "water"
    HEAT = "heat"


class BaseModel(models.Model):
    """Abstract base model with common fields."""

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(BaseModel):
    """Represents a tenant who rents a property."""

    name = fields.CharField(max_length=255, unique=True)

    meters: fields.ReverseRelation[Meter]
    invoices: fields.ReverseRelation[Invoice]

    def __str__(self) -> str:
        return self.name


class Meter(BaseModel):
    """Represents a utility meter."""

    name = fields.CharField(max_length=255)  # e.g., "Office", "Warehouse"
    resource_type = fields.CharEnumField(ResourceType, default=ResourceType.ELECTRICITY)
    tenant = fields.ForeignKeyField("models.Tenant", related_name="meters")
    subtract_from = fields.ForeignKeyField(
        "models.Meter", related_name="sub_meters", null=True, on_delete=fields.SET_NULL
    )

    readings: fields.ReverseRelation[Reading]
    tariffs: fields.ReverseRelation[Tariff]

    def __str__(self) -> str:
        return f"{self.tenant} - {self.name} " f"({self.resource_type.value})"


class Reading(BaseModel):
    """Represents a meter reading for a specific period."""

    value = fields.DecimalField(max_digits=10, decimal_places=2)
    period = fields.DateField()  # e.g., 2024-07-01 for July 2024
    meter = fields.ForeignKeyField("models.Meter", related_name="readings")

    class Meta:
        unique_together = ("meter", "period")

    def __str__(self) -> str:
        return f"Reading for {self.meter} on {self.period}: {self.value}"


class Tariff(BaseModel):
    """Represents a tariff with a specific rate for a period."""

    rate = fields.DecimalField(max_digits=10, decimal_places=4)
    period_start = fields.DateField()
    period_end = fields.DateField(null=True)
    meter = fields.ForeignKeyField("models.Meter", related_name="tariffs")

    def __str__(self) -> str:
        end_period = self.period_end or "now"
        return (
            f"Tariff for {self.meter}: {self.rate} "
            f"({self.period_start} to {end_period})"
        )


class Invoice(BaseModel):
    """Represents a bill for a tenant for a specific period."""

    amount = fields.DecimalField(max_digits=10, decimal_places=2)
    period = fields.DateField()
    tenant = fields.ForeignKeyField("models.Tenant", related_name="invoices")

    adjustments: fields.ReverseRelation[Adjustment]

    class Meta:
        unique_together = ("tenant", "period")

    def __str__(self) -> str:
        return f"Invoice for {self.tenant} on {self.period}: {self.amount}"


class Adjustment(BaseModel):
    """Represents a manual adjustment on an invoice."""

    amount = fields.DecimalField(max_digits=10, decimal_places=2)
    description = fields.CharField(max_length=255)
    invoice = fields.ForeignKeyField("models.Invoice", related_name="adjustments")

    def __str__(self) -> str:
        return (
            f"Adjustment on invoice {self.invoice_id}: "
            f"{self.amount} ({self.description})"
        )
