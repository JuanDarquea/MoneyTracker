from decimal import Decimal

import pytest

from app.services.budget_engine import compute_suggested_amount


def test_weighted_average_with_no_outlier():
    # 3:2:1 weighting: (3*90 + 2*60 + 1*30) / 6 = (270+120+30)/6 = 420/6 = 70.00
    result = compute_suggested_amount([Decimal("30.00"), Decimal("60.00"), Decimal("90.00")])
    assert result == Decimal("70.00")


def test_outlier_in_newest_month_is_trimmed():
    # median of [30, 40, 200] is 40; 200 > 2*40=80, so newest (200) is trimmed.
    # Remaining: oldest=30, middle=40, weighted 2:1 (more recent=middle):
    # (2*40 + 1*30)/3 = (80+30)/3 = 110/3 = 36.666... -> 36.67
    result = compute_suggested_amount([Decimal("30.00"), Decimal("40.00"), Decimal("200.00")])
    assert result == Decimal("36.67")


def test_outlier_in_oldest_month_is_trimmed():
    # median of [300, 40, 50] sorted [40,50,300] is 50; 300>100, so oldest (300) is trimmed.
    # Remaining: middle=40, newest=50, weighted 2:1 (newest=2, middle=1):
    # (2*50 + 1*40)/3 = (100+40)/3 = 140/3 = 46.666... -> 46.67
    result = compute_suggested_amount([Decimal("300.00"), Decimal("40.00"), Decimal("50.00")])
    assert result == Decimal("46.67")


def test_outlier_in_middle_month_is_trimmed():
    # median of [30, 300, 50] sorted [30,50,300] is 50; 300>100, so middle (300) is trimmed.
    # Remaining: oldest=30, newest=50, weighted 2:1 (newest=2, oldest=1):
    # (2*50 + 1*30)/3 = (100+30)/3 = 130/3 = 43.333... -> 43.33
    result = compute_suggested_amount([Decimal("30.00"), Decimal("300.00"), Decimal("50.00")])
    assert result == Decimal("43.33")


def test_zero_months_do_not_trigger_outlier_trim():
    # Two zero months and one spending month: the median-is-zero guard stops
    # this being treated as ">2x zero" (which would be true of any positive
    # number and would make the rule fire constantly for sparse data).
    # (3*100 + 2*0 + 1*0)/6 = 300/6 = 50.00
    result = compute_suggested_amount([Decimal("0.00"), Decimal("0.00"), Decimal("100.00")])
    assert result == Decimal("50.00")


def test_requires_exactly_three_totals():
    with pytest.raises(ValueError):
        compute_suggested_amount([Decimal("10.00"), Decimal("20.00")])
