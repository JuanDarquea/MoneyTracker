"""Pure budget-suggestion math: 3-month weighted average with outlier trimming.

No I/O, no ORM -- takes plain Decimal inputs so it can be unit tested in
isolation from the database. Eligibility (whether a line even qualifies for
a suggestion) is a separate, DB-touching concern that lives in
app.services.budget; this module always computes a number from whatever 3
totals it's given.
"""
from decimal import ROUND_HALF_UP, Decimal

_OUTLIER_MULTIPLIER = Decimal("2")
_TWO_PLACES = Decimal("0.01")


def compute_suggested_amount(monthly_totals: list[Decimal]) -> Decimal:
    """Compute a suggested budget amount from 3 months of category-tag totals.

    `monthly_totals` must have exactly 3 entries, ordered oldest to newest
    (e.g. [June, July, August] if the current month is September).

    Applies the median-deviation outlier rule: if the highest of the 3
    months is more than 2x the median of the other two, it's dropped and
    the remaining 2 months are averaged, weighted 2:1 (more recent :
    older). Otherwise, all 3 months are averaged weighted 3:2:1 (newest :
    middle : oldest).
    """
    if len(monthly_totals) != 3:
        raise ValueError("compute_suggested_amount requires exactly 3 monthly totals")

    oldest, middle, newest = monthly_totals
    highest = max(monthly_totals)
    median = sorted(monthly_totals)[1]

    # median == 0 guard: this is defense-in-depth, not a path that fires in
    # the app's normal flow. Both call sites gate on is_eligible_for_suggestion
    # first, which requires all 3 monthly totals > 0, so median can never be
    # exactly 0 when this function is actually invoked in production. Without
    # the guard, a call with a total of exactly 0.00 would treat any nonzero
    # month as "more than 2x zero" and wrongly trim it as an outlier.
    if median > 0 and highest > median * _OUTLIER_MULTIPLIER:
        if highest == oldest:
            remaining_newer, remaining_older = newest, middle
        elif highest == middle:
            remaining_newer, remaining_older = newest, oldest
        else:
            remaining_newer, remaining_older = middle, oldest
        raw = (Decimal("2") * remaining_newer + Decimal("1") * remaining_older) / Decimal("3")
    else:
        raw = (Decimal("3") * newest + Decimal("2") * middle + Decimal("1") * oldest) / Decimal("6")

    return raw.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
