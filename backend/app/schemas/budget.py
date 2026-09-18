import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import BudgetSource
from app.schemas.transaction import validate_amount


class IncomeTargetSet(BaseModel):
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_is_valid(cls, value: Decimal) -> Decimal:
        return validate_amount(value)


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
        return validate_amount(value)


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


class BudgetLineRead(BaseModel):
    category_id: uuid.UUID
    category_name: str
    is_essential: bool
    budget_amount: Decimal | None
    source: BudgetSource | None
    eligible_for_suggestion: bool
    actual_this_month: Decimal
    is_archived: bool


class BudgetState(BaseModel):
    income_target: Decimal | None
    actual_income_this_month: Decimal
    lines: list[BudgetLineRead]
    essentials_budget_total: Decimal
    discretionary_budget_total: Decimal
    essentials_actual_total: Decimal
    discretionary_actual_total: Decimal
    projected_net: Decimal | None
    actual_net_so_far: Decimal
