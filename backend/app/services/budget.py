import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, BudgetSource, CategoryType, IncomeTarget, Transaction, TransactionType
from app.schemas.budget import BudgetLineRead, BudgetLineSet, BudgetState, IncomeTargetSet, SuggestionItem
from app.services import categories as categories_service
from app.services.budget_engine import compute_suggested_amount
from app.services.date_utils import month_bounds, three_preceding_months


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


def _monthly_totals_for_line(
    db: Session, user_id: uuid.UUID, category_id: uuid.UUID, is_essential: bool, today: date
) -> list[Decimal]:
    totals = []
    for start, end in three_preceding_months(today):
        stmt = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.is_essential == is_essential,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
        total = db.scalar(stmt)
        totals.append(total if total is not None else Decimal("0.00"))
    return totals


def is_eligible_for_suggestion(monthly_totals: list[Decimal]) -> bool:
    """All 3 months must have at least one matching transaction.

    A month's total is exactly zero only when it has no matching
    transactions -- transaction amounts are always positive (enforced at
    the schema level), so a positive sum implies at least one transaction
    and a zero sum implies none.
    """
    return all(total > 0 for total in monthly_totals)


def list_suggestions(db: Session, user_id: uuid.UUID) -> list[SuggestionItem]:
    """Return a computed suggestion for every currently-eligible (category, is_essential) line."""
    today = date.today()
    categories = categories_service.list_categories(db, user_id, include_archived=False)
    suggestions = []
    for category in categories:
        if category.type != CategoryType.EXPENSE:
            continue
        for is_essential in (True, False):
            totals = _monthly_totals_for_line(db, user_id, category.id, is_essential, today)
            if is_eligible_for_suggestion(totals):
                suggestions.append(
                    SuggestionItem(
                        category_id=category.id,
                        is_essential=is_essential,
                        suggested_amount=compute_suggested_amount(totals),
                    )
                )
    return suggestions


def accept_suggestion(
    db: Session, user_id: uuid.UUID, category_id: uuid.UUID, is_essential: bool
) -> Budget | None:
    """Compute and persist a suggestion as source=computed. Returns None if the line isn't eligible."""
    today = date.today()
    totals = _monthly_totals_for_line(db, user_id, category_id, is_essential, today)
    if not is_eligible_for_suggestion(totals):
        return None
    amount = compute_suggested_amount(totals)
    line = get_budget_line(db, user_id, category_id, is_essential)
    if line is None:
        line = Budget(
            id=uuid.uuid4(),
            user_id=user_id,
            category_id=category_id,
            is_essential=is_essential,
            amount=amount,
            source=BudgetSource.COMPUTED,
        )
        db.add(line)
    else:
        line.amount = amount
        line.source = BudgetSource.COMPUTED
    db.commit()
    db.refresh(line)
    return line


def get_budget_state(db: Session, user_id: uuid.UUID, month: str) -> BudgetState:
    start, end = month_bounds(month)
    today = date.today()

    income_target = get_income_target(db, user_id)
    income_target_amount = income_target.amount if income_target is not None else None

    actual_income_this_month = db.scalar(
        select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
    ) or Decimal("0.00")

    # Every (category_id, is_essential) pair with a saved budget or any
    # transaction history (any month, not just the requested one) is shown.
    # Keyed by (category_id, is_essential); the uq_budgets_user_category_essential
    # DB constraint guarantees at most one Budget row per key, so this dict
    # construction can't silently drop or overwrite a row.
    budget_rows = {
        (row.category_id, row.is_essential): row for row in db.scalars(select(Budget).where(Budget.user_id == user_id))
    }
    tagged_pairs = set(budget_rows.keys())
    history_pairs = db.execute(
        select(Transaction.category_id, Transaction.is_essential)
        .where(Transaction.user_id == user_id, Transaction.is_essential.is_not(None))
        .distinct()
    ).all()
    tagged_pairs.update((row.category_id, row.is_essential) for row in history_pairs)

    categories_by_id = {c.id: c for c in categories_service.list_categories(db, user_id, include_archived=True)}

    lines: list[BudgetLineRead] = []
    essentials_budget_total = Decimal("0.00")
    discretionary_budget_total = Decimal("0.00")
    essentials_actual_total = Decimal("0.00")
    discretionary_actual_total = Decimal("0.00")

    for category_id, is_essential in tagged_pairs:
        category = categories_by_id.get(category_id)
        if category is None:
            continue

        budget_row = budget_rows.get((category_id, is_essential))
        budget_amount = budget_row.amount if budget_row is not None else None
        source = budget_row.source if budget_row is not None else None

        totals = _monthly_totals_for_line(db, user_id, category_id, is_essential, today)
        eligible = is_eligible_for_suggestion(totals)

        actual_this_month = db.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.category_id == category_id,
                Transaction.is_essential == is_essential,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.occurred_on >= start,
                Transaction.occurred_on <= end,
            )
        ) or Decimal("0.00")

        lines.append(
            BudgetLineRead(
                category_id=category_id,
                category_name=category.name,
                is_essential=is_essential,
                budget_amount=budget_amount,
                source=source,
                eligible_for_suggestion=eligible,
                actual_this_month=actual_this_month,
                is_archived=category.is_archived,
            )
        )

        if budget_amount is not None:
            if is_essential:
                essentials_budget_total += budget_amount
            else:
                discretionary_budget_total += budget_amount
        if is_essential:
            essentials_actual_total += actual_this_month
        else:
            discretionary_actual_total += actual_this_month

    lines.sort(key=lambda line: (line.category_name, not line.is_essential))

    projected_net = (
        income_target_amount - essentials_budget_total - discretionary_budget_total
        if income_target_amount is not None
        else None
    )

    # actual_net_so_far mirrors summary.py's `net` (income - ALL expenses this
    # month), not essentials_actual_total + discretionary_actual_total: those
    # two totals only cover transactions tagged with is_essential, so a
    # pre-M3/backfilled transaction with is_essential = NULL would otherwise
    # silently vanish from the headline net figure.
    total_actual_expense_this_month = db.scalar(
        select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
    ) or Decimal("0.00")
    actual_net_so_far = actual_income_this_month - total_actual_expense_this_month

    return BudgetState(
        income_target=income_target_amount,
        actual_income_this_month=actual_income_this_month,
        lines=lines,
        essentials_budget_total=essentials_budget_total,
        discretionary_budget_total=discretionary_budget_total,
        essentials_actual_total=essentials_actual_total,
        discretionary_actual_total=discretionary_actual_total,
        projected_net=projected_net,
        actual_net_so_far=actual_net_so_far,
    )
