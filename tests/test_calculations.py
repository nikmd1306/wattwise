"""Tests for core calculation functions."""

from decimal import Decimal

import pytest

from app.core.calculations import calculate_consumption, calculate_cost


@pytest.mark.parametrize(
    "current, previous, adjustment, expected",
    [
        (Decimal("100"), Decimal("50"), Decimal("0"), Decimal("50")),
        (Decimal("100"), Decimal("50"), Decimal("10"), Decimal("40")),
        (Decimal("50"), Decimal("100"), Decimal("10"), Decimal("0")),
        (Decimal("100"), Decimal("100"), Decimal("0"), Decimal("0")),
        (Decimal("150.55"), Decimal("120.25"), Decimal("10.10"), Decimal("20.20")),
        (Decimal("100"), Decimal("50"), Decimal("60"), Decimal("-10")),
    ],
)
def test_calculate_consumption(current, previous, adjustment, expected):
    """Tests the calculate_consumption function with various scenarios."""
    assert calculate_consumption(current, previous, adjustment) == expected


@pytest.mark.parametrize(
    "consumption, rate, expected",
    [
        (Decimal("100"), Decimal("10.5"), Decimal("1050")),
        (Decimal("0"), Decimal("10.5"), Decimal("0")),
        (Decimal("100"), Decimal("0"), Decimal("0")),
        (Decimal("30.30"), Decimal("40.00"), Decimal("1212.00")),
    ],
)
def test_calculate_cost(consumption, rate, expected):
    """Tests the calculate_cost function with various scenarios."""
    assert calculate_cost(consumption, rate) == expected
