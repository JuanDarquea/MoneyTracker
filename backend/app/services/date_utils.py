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
