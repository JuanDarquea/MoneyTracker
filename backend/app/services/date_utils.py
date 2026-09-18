import calendar
from datetime import date


def month_bounds(month: str) -> tuple[date, date]:
    """Return (start, end) dates for a 'YYYY-MM' string, inclusive."""
    year_str, month_str = month.split("-")
    year, month_num = int(year_str), int(month_str)
    start = date(year, month_num, 1)
    last_day = calendar.monthrange(year, month_num)[1]
    end = date(year, month_num, last_day)
    return start, end


def three_preceding_months(today: date) -> list[tuple[date, date]]:
    """Return (start, end) bounds for the 3 calendar months before `today`'s month, oldest first."""
    bounds = []
    year, month = today.year, today.month
    for _ in range(3):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        last_day = calendar.monthrange(year, month)[1]
        bounds.append((date(year, month, 1), date(year, month, last_day)))
    return list(reversed(bounds))
