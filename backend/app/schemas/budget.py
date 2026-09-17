import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import BudgetSource
from app.schemas.transaction import _validate_amount


class IncomeTargetSet(BaseModel):
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_is_valid(cls, value: Decimal) -> Decimal:
        return _validate_amount(value)


class IncomeTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount: Decimal


class BudgetLineSet(BaseModel):
    category_id: uuid.UUID
    is_essential: bool
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_is_valid(cls, value: Decimal) -> Decimal:
        return _validate_amount(value)


class BudgetLineWriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: uuid.UUID
    is_essential: bool
    amount: Decimal
    source: BudgetSource


class AcceptSuggestionRequest(BaseModel):
    category_id: uuid.UUID
    is_essential: bool


class SuggestionItem(BaseModel):
    category_id: uuid.UUID
    is_essential: bool
    suggested_amount: Decimal
