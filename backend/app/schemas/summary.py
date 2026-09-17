import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models import CategoryType


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID
    category_name: str
    type: CategoryType
    amount: Decimal


class MonthlySummary(BaseModel):
    month: str
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    by_category: list[CategoryBreakdownItem]
