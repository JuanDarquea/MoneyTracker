import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import TransactionType


def _validate_amount(value: Decimal) -> Decimal:
    """Validate amount is positive and has at most 2 decimal places."""
    if value <= 0:
        raise ValueError("amount must be greater than zero")
    if value.as_tuple().exponent < -2:
        raise ValueError("amount must have at most 2 decimal places")
    return value


class TransactionBase(BaseModel):
    category_id: uuid.UUID
    type: TransactionType
    amount: Decimal
    occurred_on: date
    note: str | None = None
    is_essential: bool | None = None

    @field_validator("amount")
    @classmethod
    def amount_is_positive_with_two_decimals(cls, value: Decimal) -> Decimal:
        return _validate_amount(value)


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    type: TransactionType | None = None
    amount: Decimal | None = None
    occurred_on: date | None = None
    note: str | None = None
    is_essential: bool | None = None

    @field_validator("amount", mode="after")
    @classmethod
    def validate_amount_if_provided(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return _validate_amount(value)


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
