from datetime import date
from decimal import Decimal

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




def test_february_month_bounds():
    start, next_month = month_bounds(2026, 2)

    assert start == date(2026, 2, 1)
    assert next_month == date(2026, 3, 1)