import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, BudgetSource, IncomeTarget
from app.schemas.budget import BudgetLineSet, IncomeTargetSet


def get_income_target(db: Session, user_id: uuid.UUID) -> IncomeTarget | None:
    stmt = select(IncomeTarget).where(IncomeTarget.user_id == user_id)
    return db.scalars(stmt).first()


def set_income_target(db: Session, user_id: uuid.UUID, payload: IncomeTargetSet) -> IncomeTarget:
    target = get_income_target(db, user_id)
    if target is None:
        target = IncomeTarget(id=uuid.uuid4(), user_id=user_id, amount=payload.amount)
        db.add(target)
    else:
        target.amount = payload.amount
    db.commit()
    db.refresh(target)
    return target


def get_budget_line(db: Session, user_id: uuid.UUID, category_id: uuid.UUID, is_essential: bool) -> Budget | None:
    stmt = select(Budget).where(
        Budget.user_id == user_id,
        Budget.category_id == category_id,
        Budget.is_essential == is_essential,
    )
    return db.scalars(stmt).first()


def set_budget_line(db: Session, user_id: uuid.UUID, payload: BudgetLineSet) -> Budget:
    line = get_budget_line(db, user_id, payload.category_id, payload.is_essential)
    if line is None:
        line = Budget(
            id=uuid.uuid4(),
            user_id=user_id,
            category_id=payload.category_id,
            is_essential=payload.is_essential,
            amount=payload.amount,
            source=BudgetSource.MANUAL,
        )
        db.add(line)
    else:
        line.amount = payload.amount
        line.source = BudgetSource.MANUAL
    db.commit()
    db.refresh(line)
    return line
