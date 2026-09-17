from datetime import date

from app.services.date_utils import month_bounds


def test_month_bounds_returns_first_and_last_day():
    start, end = month_bounds("2026-02")
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_month_bounds_handles_31_day_month():
    start, end = month_bounds("2026-01")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)
