from datetime import date
from decimal import Decimal

import pytest

from services.import_service import tx_fingerprint
from services.report_service import month_bounds

def test_same_transaction_produces_same_fingerprint():
    first = tx_fingerprint(
        1,
        date(2026, 2, 11),
        Decimal("-28.11"),
        "Copper Cup Cafe",
        "Demo card payment",
    )

    second = tx_fingerprint(
        1,
        date(2026, 2, 11),
        Decimal("-28.11"),
        "Copper Cup Cafe",
        "Demo card payment",
    )

    assert first == second


def test_december_rolls_into_next_year():
    start, next_month = month_bounds(2026, 12)

    assert start == date(2026, 12, 1)
    assert next_month == date(2027, 1, 1)


def test_invalid_month_raises_error():
    with pytest.raises(ValueError):
        month_bounds(2026, 13)


def test_different_amount_changes_fingerprint():
    first = tx_fingerprint(
        1, date(2026, 2, 11), Decimal("-20.00"),
        "Copper Cup Cafe", "Demo payment"
    )

    second = tx_fingerprint(
        1, date(2026, 2, 11), Decimal("-25.00"),
        "Copper Cup Cafe", "Demo payment"
    )

    assert first != second




def test_february_month_bounds():
    start, next_month = month_bounds(2026, 2)

    assert start == date(2026, 2, 1)
    assert next_month == date(2026, 3, 1)