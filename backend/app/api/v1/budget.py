import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import CategoryType
from app.schemas.budget import BudgetLineSet, BudgetLineWriteRead, IncomeTargetRead, IncomeTargetSet
from app.services import budget as budget_service
from app.services import categories as categories_service

router = APIRouter(prefix="/budget", tags=["budget"])


@router.put("/income-target", response_model=IncomeTargetRead)
def set_income_target(
    payload: IncomeTargetSet,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return budget_service.set_income_target(db, user_id, payload)


@router.put("/lines", response_model=BudgetLineWriteRead)
def set_budget_line(
    payload: BudgetLineSet,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    category = categories_service.get_category(db, user_id, payload.category_id)
    if category is None or category.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if category.type != CategoryType.EXPENSE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Budgets can only be set on expense categories",
        )
    return budget_service.set_budget_line(db, user_id, payload)
