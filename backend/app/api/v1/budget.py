import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import CategoryType
from app.schemas.budget import (
    AcceptSuggestionRequest,
    BudgetLineSet,
    BudgetLineWriteRead,
    BudgetState,
    IncomeTargetRead,
    IncomeTargetSet,
    SuggestionItem,
)
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


@router.get("/suggestions", response_model=list[SuggestionItem])
def get_suggestions(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return budget_service.list_suggestions(db, user_id)


@router.post("/lines/accept-suggestion", response_model=BudgetLineWriteRead)
def accept_suggestion(
    payload: AcceptSuggestionRequest,
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
    line = budget_service.accept_suggestion(db, user_id, payload.category_id, payload.is_essential)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Not enough transaction history for a suggestion yet",
        )
    return line


@router.get("", response_model=BudgetState)
def get_budget(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    if month is None:
        today = date.today()
        month = f"{today.year:04d}-{today.month:02d}"
    return budget_service.get_budget_state(db, user_id, month)
