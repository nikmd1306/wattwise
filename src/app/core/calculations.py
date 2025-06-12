"""Core business logic for calculations."""

from __future__ import annotations

from decimal import Decimal


def calculate_consumption(
    current_reading: Decimal,
    previous_reading: Decimal,
    adjustment: Decimal = Decimal("0"),
) -> Decimal:
    """
    Calculates the consumption between two meter readings, applying an adjustment.

    Args:
        current_reading: The most recent meter reading.
        previous_reading: The previous meter reading.
        adjustment: A value to subtract from the raw consumption.

    Returns:
        The calculated consumption. Returns 0 if current reading
        is less than previous (e.g., meter reset).
    """
    if current_reading < previous_reading:
        # This could happen if a meter is replaced or resets.
        # For now, we assume consumption is 0 in this case.
        # A more advanced implementation might log a warning.
        return Decimal("0")

    raw_consumption = current_reading - previous_reading
    return raw_consumption - adjustment


def calculate_cost(consumption: Decimal, rate: Decimal) -> Decimal:
    """
    Calculates the monetary cost based on consumption and a tariff rate.

    Args:
        consumption: The amount of resource consumed.
        rate: The monetary rate per unit of consumption.

    Returns:
        The calculated cost.
    """
    return consumption * rate
