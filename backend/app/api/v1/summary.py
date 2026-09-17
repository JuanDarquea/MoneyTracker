import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.summary import MonthlySummary
from app.services import summary as summary_service

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=MonthlySummary)
def get_summary(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    if month is None:
        today = date.today()
        month = f"{today.year:04d}-{today.month:02d}"
    return summary_service.get_monthly_summary(db, user_id, month)
