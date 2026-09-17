import calendar
import uuid
from decimal import Decimal
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction, TransactionType
from app.schemas.summary import CategoryBreakdownItem, MonthlySummary


def _month_bounds(month: str) -> tuple[date, date]:
    year_str, month_str = month.split("-")
    year, month_num = int(year_str), int(month_str)
    start = date(year, month_num, 1)
    last_day = calendar.monthrange(year, month_num)[1]
    end = date(year, month_num, last_day)
    return start, end


def get_monthly_summary(db: Session, user_id: uuid.UUID, month: str) -> MonthlySummary:
    start, end = _month_bounds(month)

    stmt = (
        select(
            Category.id,
            Category.name,
            Transaction.type,
            func.sum(Transaction.amount).label("amount"),
        )
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
        .group_by(Category.id, Category.name, Transaction.type)
        .order_by(Category.name)
    )
    rows = db.execute(stmt).all()

    by_category = [
        CategoryBreakdownItem(category_id=row.id, category_name=row.name, type=row.type, amount=row.amount)
        for row in rows
    ]

    total_income = sum(
        (item.amount for item in by_category if item.type == TransactionType.INCOME), Decimal("0.00")
    )
    total_expense = sum(
        (item.amount for item in by_category if item.type == TransactionType.EXPENSE), Decimal("0.00")
    )

    return MonthlySummary(
        month=month,
        total_income=total_income,
        total_expense=total_expense,
        net=total_income - total_expense,
        by_category=by_category,
    )
