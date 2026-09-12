from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import TransactionType
from app.schemas.transaction import TransactionCreate


def test_amount_is_decimal_not_float():
    payload = TransactionCreate(
        category_id="11111111-1111-1111-1111-111111111111",
        type=TransactionType.EXPENSE,
        amount="19.99",
        occurred_on="2026-09-01",
    )
    assert isinstance(payload.amount, Decimal)
    assert payload.amount == Decimal("19.99")


def test_amount_rejects_more_than_two_decimal_places():
    with pytest.raises(ValidationError):
        TransactionCreate(
            category_id="11111111-1111-1111-1111-111111111111",
            type=TransactionType.EXPENSE,
            amount="19.995",
            occurred_on="2026-09-01",
        )


def test_amount_must_be_positive():
    with pytest.raises(ValidationError):
        TransactionCreate(
            category_id="11111111-1111-1111-1111-111111111111",
            type=TransactionType.EXPENSE,
            amount="-5.00",
            occurred_on="2026-09-01",
        )
