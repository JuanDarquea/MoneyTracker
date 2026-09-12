from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import TransactionType
from app.schemas.transaction import TransactionCreate, TransactionUpdate


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


def test_amount_from_json_deserialization():
    """Test that JSON float number deserializes to exact Decimal without float corruption."""
    json_payload = '{"category_id": "11111111-1111-1111-1111-111111111111", "type": "expense", "amount": 19.99, "occurred_on": "2026-09-01"}'
    payload = TransactionCreate.model_validate_json(json_payload)
    assert isinstance(payload.amount, Decimal)
    assert payload.amount == Decimal("19.99")


def test_transaction_update_accepts_valid_amount():
    """Test that TransactionUpdate accepts a valid partial update with just amount."""
    update = TransactionUpdate(amount="25.50")
    assert isinstance(update.amount, Decimal)
    assert update.amount == Decimal("25.50")


def test_transaction_update_rejects_negative_amount():
    """Test that TransactionUpdate rejects a negative amount."""
    with pytest.raises(ValidationError):
        TransactionUpdate(amount="-5.00")


def test_transaction_update_rejects_amount_with_more_than_two_decimals():
    """Test that TransactionUpdate rejects amount with more than 2 decimal places."""
    with pytest.raises(ValidationError):
        TransactionUpdate(amount="19.999")
