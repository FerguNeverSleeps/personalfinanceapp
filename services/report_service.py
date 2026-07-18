from datetime import date


def month_bounds(year: int, month: int):
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")

    start_date = date(year, month, 1)

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    return start_date, next_month
