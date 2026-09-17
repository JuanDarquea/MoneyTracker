# M3 — Budget Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the essential/discretionary tag from category to transaction, then build the 3-month weighted-average budget suggestion engine (cold-start + computed, essentials/discretionary split) and its Budget tab.

**Architecture:** FastAPI service layer gains a pure math module (`budget_engine.py`) for the weighted-average/outlier-trim algorithm, a DB-touching `budget.py` service for CRUD + aggregation, and a `budget.py` router exposing 5 endpoints. Flutter gains a `budget` feature (models/provider/screen) and a 4th nav tab, plus edits to the existing category/transaction UI to relocate the essential tag.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, pytest (backend); Flutter, Riverpod, `flutter_test` (frontend). Same stack as M1/M2, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-17-m3-budget-engine-design.md`

## Global Constraints

- All money fields are `Decimal`, never `float` (`Numeric(12, 2)` columns).
- Budget suggestion amounts are quantized to 2 places with `ROUND_HALF_UP` (see spec's Backend Algorithm section — this is the first explicit rounding call in the codebase).
- `is_essential` is nullable at the DB level (only meaningful for expense transactions) but required by API validation for every expense transaction and forbidden for income transactions.
- Weighting is 3:2:1 (newest:middle:oldest); outlier trim is the median-deviation rule (highest month > 2× median of the other two → drop it, average the remaining 2 weighted 2:1).
- Cold-start eligibility is per `(category_id, is_essential)` line: all 3 of the calendar months immediately preceding the current month must each have ≥1 matching transaction.
- Budgets are standing targets — nothing auto-resets them monthly.
- After every task: run `python -m pytest` from `backend/` (not bare `pytest` — this repo has no `pythonpath` config, so the bare command fails with `ModuleNotFoundError: No module named 'app'`) for backend tasks, and `flutter test` from `frontend/money_tracker_app/` for frontend tasks.
- **Manual click-through is required** after Tasks 1, 5, and 7 (the points where a real end-to-end flow becomes exercisable) — log in for real, hit the real backend and Supabase project, verify the feature actually works, before moving on. This is a standing project rule, not optional polish.

---

## Task 1: Move `is_essential` from Category to Transaction

**Files:**
- Modify: `backend/app/models/category.py`
- Modify: `backend/app/models/transaction.py`
- Modify: `backend/app/schemas/category.py`
- Modify: `backend/app/schemas/transaction.py`
- Modify: `backend/app/services/categories.py`
- Modify: `backend/app/api/v1/categories.py`
- Modify: `backend/app/api/v1/transactions.py`
- Create: `backend/alembic/versions/0003_transaction_essential_tag.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_categories_api.py`
- Modify: `backend/tests/test_category_schemas.py`
- Modify: `backend/tests/test_transactions_api.py`
- Modify: `backend/tests/test_summary_api.py`

**Interfaces:**
- Produces: `Transaction.is_essential: bool | None` (model field), `TransactionCreate.is_essential: bool | None` / `TransactionUpdate.is_essential: bool | None` (schema fields). Every later task that creates transactions in tests must pass `is_essential` for expense transactions.
- Consumes: nothing from earlier tasks (this is Task 1).

This task touches a lot of already-passing tests because every existing expense-transaction payload in the test suite must now include `is_essential`, or it will start failing 422 once the router enforces it. Each step below shows the complete resulting file where the changes are non-trivial.

- [ ] **Step 1: Remove `is_essential` from the Category model**

Edit `backend/app/models/category.py` — delete the `is_essential` line so the file reads:

```python
import enum
import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType, name="category_type", values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Add `is_essential` to the Transaction model**

Edit `backend/app/models/transaction.py` so it reads:

```python
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Date, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transaction_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    is_essential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: Create the migration**

Create `backend/alembic/versions/0003_transaction_essential_tag.py`:

```python
"""move essential/discretionary tag from categories to transactions

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Essential/discretionary now varies per-transaction (a single category
    # like Food mixes groceries and dining out), not per-category. Existing
    # transactions have no historical tag -- they're backfilled to NULL
    # ("unclassified") rather than a guessed default; the budget engine
    # simply skips NULL rows rather than inventing history that was never
    # recorded.
    op.add_column("transactions", sa.Column("is_essential", sa.Boolean(), nullable=True))
    op.drop_column("categories", "is_essential")


def downgrade() -> None:
    # Cannot restore the original per-category values (same caveat as
    # migration 0002's downgrade not restoring deleted rows).
    op.add_column("categories", sa.Column("is_essential", sa.Boolean(), nullable=True))
    op.drop_column("transactions", "is_essential")
```

- [ ] **Step 4: Update category schemas — remove `is_essential`**

Edit `backend/app/schemas/category.py` so it reads:

```python
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import CategoryType


def _validate_name(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 64:
        raise ValueError("name must be between 1 and 64 characters")
    return value


class CategoryBase(BaseModel):
    name: str
    type: CategoryType

    @field_validator("name")
    @classmethod
    def name_is_valid(cls, value: str) -> str:
        return _validate_name(value)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None

    @field_validator("name")
    @classmethod
    def name_is_valid_if_provided(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_name(value)


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: CategoryType
    is_archived: bool
```

- [ ] **Step 5: Add `is_essential` to transaction schemas**

Edit `backend/app/schemas/transaction.py` so it reads:

```python
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
```

Note: no schema-level "required for expense" validator is added here — like the existing type/category coherence check, that rule is enforced in the router (Steps 7-8), because `TransactionUpdate` is a partial payload and the rule depends on the transaction's *effective* type, which the schema alone can't know.

- [ ] **Step 6: Remove `is_essential` from the category service**

Edit `backend/app/services/categories.py` so it reads:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, CategoryType
from app.schemas.category import CategoryCreate, CategoryUpdate

DEFAULT_CATEGORIES: list[tuple[str, CategoryType]] = [
    ("Salary", CategoryType.INCOME),
    ("Food", CategoryType.EXPENSE),
    ("Transport", CategoryType.EXPENSE),
    ("Housing", CategoryType.EXPENSE),
    ("Utilities", CategoryType.EXPENSE),
    ("Entertainment", CategoryType.EXPENSE),
    ("Shopping", CategoryType.EXPENSE),
]


def ensure_default_categories(db: Session, user_id: uuid.UUID) -> None:
    """Create this user's 7 starter categories if they have none yet.

    Idempotent: a user who already has any category (even just a custom
    one) is left untouched -- this only fires for a brand new user.
    """
    stmt = select(Category.id).where(Category.user_id == user_id).limit(1)
    if db.scalars(stmt).first() is not None:
        return

    for name, cat_type in DEFAULT_CATEGORIES:
        db.add(
            Category(
                id=uuid.uuid4(),
                user_id=user_id,
                name=name,
                type=cat_type,
            )
        )
    db.commit()


def list_categories(db: Session, user_id: uuid.UUID, include_archived: bool = False) -> list[Category]:
    ensure_default_categories(db, user_id)
    stmt = select(Category).where(Category.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(Category.is_archived.is_(False))
    stmt = stmt.order_by(Category.name)
    return list(db.scalars(stmt))


def get_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
    stmt = select(Category).where(Category.id == category_id, Category.user_id == user_id)
    return db.scalars(stmt).first()


def create_category(db: Session, user_id: uuid.UUID, payload: CategoryCreate) -> Category:
    category = Category(id=uuid.uuid4(), user_id=user_id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: Category, payload: CategoryUpdate) -> Category:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category
```

- [ ] **Step 7: Remove the `is_essential` check from the category router**

Edit `backend/app/api/v1/categories.py` so it reads:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import categories as categories_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
def list_categories(
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return categories_service.list_categories(db, user_id, include_archived=include_archived)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return categories_service.create_category(db, user_id, payload)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    category = categories_service.get_category(db, user_id, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return categories_service.update_category(db, category, payload)
```

- [ ] **Step 8: Add `is_essential` coherence checks to the transaction router**

Edit `backend/app/api/v1/transactions.py` so it reads:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import TransactionType
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services import categories as categories_service
from app.services import transactions as transactions_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _check_is_essential_coherence(effective_type: TransactionType, effective_is_essential: bool | None) -> None:
    if effective_type == TransactionType.EXPENSE and effective_is_essential is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="is_essential is required for expense transactions",
        )
    if effective_type == TransactionType.INCOME and effective_is_essential is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="is_essential cannot be set on an income transaction",
        )


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    category = categories_service.get_category(db, user_id, payload.category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if payload.type != category.type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transaction type must match the category's type",
        )
    _check_is_essential_coherence(payload.type, payload.is_essential)
    return transactions_service.create_transaction(db, user_id, payload)


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return transactions_service.list_transactions(db, user_id)


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    txn = transactions_service.get_transaction(db, user_id, transaction_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    txn = transactions_service.get_transaction(db, user_id, transaction_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    effective_type = payload.type if payload.type is not None else txn.type

    if payload.category_id is not None:
        # category_id is changing (type may or may not be changing alongside it):
        # validate the *new* category against whichever type will end up in effect.
        category = categories_service.get_category(db, user_id, payload.category_id)
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        if effective_type != category.type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction type must match the category's type",
            )
    elif payload.type is not None:
        # type is changing but category_id is not: validate the new type against the
        # transaction's existing category.
        category = categories_service.get_category(db, user_id, txn.category_id)
        if category is not None and payload.type != category.type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transaction type must match the category's type",
            )

    effective_is_essential = (
        payload.is_essential if "is_essential" in payload.model_fields_set else txn.is_essential
    )
    _check_is_essential_coherence(effective_type, effective_is_essential)

    return transactions_service.update_transaction(db, txn, payload)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    txn = transactions_service.get_transaction(db, user_id, transaction_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    transactions_service.delete_transaction(db, txn)
```

- [ ] **Step 9: Update `conftest.py` fixtures**

Edit `backend/tests/conftest.py` — remove `is_essential=...` from all three `Category(...)` constructions (`seeded_category`, `seeded_income_category`, `other_user_category`):

```python
@pytest.fixture()
def seeded_category(db: Session, user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Food",
        type=CategoryType.EXPENSE,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture()
def seeded_income_category(db: Session, user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Salary",
        type=CategoryType.INCOME,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture()
def other_user_category(db: Session, other_user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        user_id=other_user_id,
        name="Rent",
        type=CategoryType.EXPENSE,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
```

Leave the rest of the file (`client`, `user_id`, `auth_headers`, `db`, `other_user_id` fixtures) unchanged.

- [ ] **Step 10: Run the backend tests and see what's now broken**

Run: `cd backend && python -m pytest -q`
Expected: several failures — `test_categories_api.py`'s essential-specific tests (schema no longer has the field), and `test_transactions_api.py` / `test_summary_api.py` tests that POST expense transactions without `is_essential` (now 422 instead of 201/200).

- [ ] **Step 11: Fix `test_categories_api.py` — delete the essential-specific tests**

Edit `backend/tests/test_categories_api.py`: delete `test_create_category_rejects_is_essential_on_income` and `test_update_category_rejects_is_essential_on_income` entirely (no replacement — that rule no longer exists), and simplify the payloads in `test_create_category` and `test_update_category_name_and_essential`. Resulting file:

```python
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

DEFAULT_CATEGORY_NAMES = {"Salary", "Food", "Transport", "Housing", "Utilities", "Entertainment", "Shopping"}


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.supabase_jwt_aud,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_list_categories_lazily_seeds_defaults(client, auth_headers):
    response = client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == DEFAULT_CATEGORY_NAMES


def test_list_categories_lazy_seed_is_idempotent(client, auth_headers):
    client.get("/api/v1/categories", headers=auth_headers)
    second_response = client.get("/api/v1/categories", headers=auth_headers)
    assert len(second_response.json()) == 7


def test_create_category(client, auth_headers):
    response = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Gym"
    assert created["is_archived"] is False


def test_update_category_name(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense"},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"name": "Gym Membership"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Gym Membership"


def test_archive_category_hides_it_from_default_list(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense"},
        headers=auth_headers,
    ).json()

    archive_response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"is_archived": True},
        headers=auth_headers,
    )
    assert archive_response.status_code == 200

    default_list = client.get("/api/v1/categories", headers=auth_headers)
    assert created["id"] not in {item["id"] for item in default_list.json()}

    full_list = client.get("/api/v1/categories?include_archived=true", headers=auth_headers)
    assert created["id"] in {item["id"] for item in full_list.json()}


def test_categories_are_isolated_between_users(client, auth_headers):
    user_a_category = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense"},
        headers=auth_headers,
    ).json()

    user_b_headers = _auth_headers_for(uuid.uuid4())
    user_b_list = client.get("/api/v1/categories", headers=user_b_headers).json()

    assert user_a_category["id"] not in {item["id"] for item in user_b_list}
    assert {item["name"] for item in user_b_list} == DEFAULT_CATEGORY_NAMES

    patch_response = client.patch(
        f"/api/v1/categories/{user_a_category['id']}",
        json={"name": "Hijacked"},
        headers=user_b_headers,
    )
    assert patch_response.status_code == 404
```

- [ ] **Step 12: Fix `test_category_schemas.py`**

Edit `backend/tests/test_category_schemas.py`: delete `test_create_expense_category_with_essential_flag` and `test_create_income_category_rejects_is_essential`; remove `is_essential` from the `FakeOrmCategory` stand-in. Resulting file:

```python
import uuid

import pytest
from pydantic import ValidationError

from app.models import CategoryType
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate


def test_create_category_rejects_blank_name():
    with pytest.raises(ValidationError):
        CategoryCreate(name="   ", type=CategoryType.EXPENSE)


def test_create_category_rejects_name_over_64_chars():
    with pytest.raises(ValidationError):
        CategoryCreate(name="x" * 65, type=CategoryType.EXPENSE)


def test_update_allows_partial_fields():
    update = CategoryUpdate(is_archived=True)
    assert update.name is None
    assert update.is_archived is True


def test_update_rejects_blank_name_if_provided():
    with pytest.raises(ValidationError):
        CategoryUpdate(name="")


def test_read_from_orm_attributes():
    class FakeOrmCategory:
        id = uuid.uuid4()
        name = "Food"
        type = CategoryType.EXPENSE
        is_archived = False

    read = CategoryRead.model_validate(FakeOrmCategory())
    assert read.name == "Food"
    assert read.is_archived is False
```

- [ ] **Step 13: Add `is_essential` to every expense-transaction payload in `test_transactions_api.py`**

Edit `backend/tests/test_transactions_api.py`, adding `"is_essential": True` (or `False` — either is fine, these tests don't test the tag itself) to every JSON payload where `"type": "expense"` appears. The full corrected file:

```python
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt

from app.core.config import get_settings


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    """Mint a valid Supabase-style JWT for an arbitrary user_id.

    Mirrors the `auth_headers` fixture in conftest.py but lets a test mint a
    second, independent, valid token for a different user.
    """
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.supabase_jwt_aud,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_create_transaction_requires_auth(client, seeded_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "12.50",
            "occurred_on": "2026-09-01",
            "is_essential": True,
        },
    )
    assert response.status_code == 401


def test_create_and_get_transaction(client, auth_headers, seeded_category):
    create_response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "12.50",
            "occurred_on": "2026-09-01",
            "note": "Lunch",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["amount"] == "12.50"

    get_response = client.get(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["note"] == "Lunch"


def test_list_transactions_scoped_to_user(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    )

    other_user_response = client.get("/api/v1/transactions", headers={"Authorization": "Bearer not-this-users-token"})
    assert other_user_response.status_code == 401

    own_list_response = client.get("/api/v1/transactions", headers=auth_headers)
    assert own_list_response.status_code == 200
    assert len(own_list_response.json()) == 1


def test_update_transaction(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    update_response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"amount": "7.25"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == "7.25"


def test_delete_transaction(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    delete_response = client.delete(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 404


def test_create_transaction_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(other_user_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_transaction_rejects_other_users_category(client, auth_headers, seeded_category, other_user_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(other_user_category.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_transactions_are_isolated_between_users(client, auth_headers, seeded_category, other_user_id, other_user_category):
    """Two real, independently-authenticated users must never see or touch each other's data."""
    user_b_headers = _auth_headers_for(other_user_id)

    user_a_transaction = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "note": "User A lunch",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    user_b_transaction = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(other_user_category.id),
            "type": "expense",
            "amount": "99.00",
            "occurred_on": "2026-09-03",
            "note": "User B rent",
            "is_essential": True,
        },
        headers=user_b_headers,
    ).json()

    # User A's list contains only their own transaction, never user B's.
    user_a_list = client.get("/api/v1/transactions", headers=auth_headers)
    assert user_a_list.status_code == 200
    user_a_ids = {item["id"] for item in user_a_list.json()}
    assert user_a_ids == {user_a_transaction["id"]}
    assert user_b_transaction["id"] not in user_a_ids

    # User A cannot fetch, patch, or delete user B's transaction by id (404, not 403 --
    # preserving "don't leak existence" semantics used elsewhere in this file).
    get_response = client.get(f"/api/v1/transactions/{user_b_transaction['id']}", headers=auth_headers)
    assert get_response.status_code == 404

    patch_response = client.patch(
        f"/api/v1/transactions/{user_b_transaction['id']}",
        json={"amount": "1.00"},
        headers=auth_headers,
    )
    assert patch_response.status_code == 404

    delete_response = client.delete(f"/api/v1/transactions/{user_b_transaction['id']}", headers=auth_headers)
    assert delete_response.status_code == 404

    # User B's transaction is untouched and still visible to user B.
    user_b_get = client.get(f"/api/v1/transactions/{user_b_transaction['id']}", headers=user_b_headers)
    assert user_b_get.status_code == 200
    assert user_b_get.json()["amount"] == "99.00"


def test_create_transaction_rejects_type_category_mismatch(client, auth_headers, seeded_category):
    """seeded_category is an expense category; declaring the transaction as income must be rejected."""
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "income",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_transaction_type_alone_rejects_mismatch_with_existing_category(
    client, auth_headers, seeded_category
):
    """Changing only `type` on a transaction must be validated against its current category."""
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"type": "income"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_transaction_category_id_alone_rejects_mismatch_with_existing_type(
    client, auth_headers, seeded_category, seeded_income_category
):
    """Changing only `category_id` on a transaction must be validated against its current type."""
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(seeded_income_category.id)},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_transaction_category_and_type_together_allows_consistent_pair(
    client, auth_headers, seeded_category, seeded_income_category
):
    """Changing category_id and type together to a consistent income pair should succeed."""
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(seeded_income_category.id), "type": "income", "is_essential": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "income"
    assert response.json()["category_id"] == str(seeded_income_category.id)
    assert response.json()["is_essential"] is None


def test_create_expense_transaction_without_is_essential_is_rejected(client, auth_headers, seeded_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_income_transaction_with_is_essential_is_rejected(client, auth_headers, seeded_income_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_income_category.id),
            "type": "income",
            "amount": "1000.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_can_change_is_essential_alone(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"is_essential": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_essential"] is False


def test_update_cannot_clear_is_essential_on_an_expense_transaction(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"is_essential": None},
        headers=auth_headers,
    )
    assert response.status_code == 422
```

Note the change to `test_update_transaction_category_and_type_together_allows_consistent_pair`: it now explicitly clears `is_essential` to `None` in the same request that switches the transaction to income — without that, `effective_is_essential` would carry over the transaction's existing `True` value onto an income-typed transaction and get rejected by the new coherence check. That's the correct, intentional behavior (surfaced by `test_update_cannot_clear_is_essential_on_an_expense_transaction`'s mirror-image case): a client changing type must explicitly manage `is_essential` in the same request.

- [ ] **Step 14: Add `is_essential` to every expense-transaction payload in `test_summary_api.py`**

Edit `backend/tests/test_summary_api.py`, adding `"is_essential": True` to the two expense-transaction payloads inside `test_summary_aggregates_by_category_and_type` and to the single expense payloads in `test_summary_defaults_to_current_month` and `test_summary_is_isolated_between_users`:

```python
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.supabase_jwt_aud,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_summary_for_empty_month_returns_zeroed_totals(client, auth_headers):
    response = client.get("/api/v1/summary?month=2020-01", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2020-01"
    assert body["total_income"] == "0.00"
    assert body["total_expense"] == "0.00"
    assert body["net"] == "0.00"
    assert body["by_category"] == []


def test_summary_aggregates_by_category_and_type(client, auth_headers, seeded_category, seeded_income_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "20.00", "occurred_on": "2026-09-05", "is_essential": True},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "15.50", "occurred_on": "2026-09-10", "is_essential": False},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_income_category.id), "type": "income", "amount": "1000.00", "occurred_on": "2026-09-01"},
        headers=auth_headers,
    )
    # Outside the queried month -- must not be included.
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "999.00", "occurred_on": "2026-08-15", "is_essential": True},
        headers=auth_headers,
    )

    response = client.get("/api/v1/summary?month=2026-09", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == "1000.00"
    assert body["total_expense"] == "35.50"
    assert body["net"] == "964.50"

    by_category = {item["category_name"]: item["amount"] for item in body["by_category"]}
    assert by_category["Food"] == "35.50"
    assert by_category["Salary"] == "1000.00"


def test_summary_defaults_to_current_month(client, auth_headers, seeded_category):
    from datetime import date

    today = date.today().isoformat()
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "10.00", "occurred_on": today, "is_essential": True},
        headers=auth_headers,
    )

    response = client.get("/api/v1/summary", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total_expense"] == "10.00"


def test_summary_rejects_invalid_month_value(client, auth_headers):
    response = client.get("/api/v1/summary?month=2026-13", headers=auth_headers)
    assert response.status_code == 422

    response = client.get("/api/v1/summary?month=2026-00", headers=auth_headers)
    assert response.status_code == 422


def test_summary_is_isolated_between_users(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "50.00", "occurred_on": "2026-09-05", "is_essential": True},
        headers=auth_headers,
    )

    other_headers = _auth_headers_for(uuid.uuid4())
    response = client.get("/api/v1/summary?month=2026-09", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["total_expense"] == "0.00"
```

- [ ] **Step 15: Run the full backend test suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS, all tests green.

- [ ] **Step 16: Commit**

```bash
git add backend/app/models/category.py backend/app/models/transaction.py \
  backend/app/schemas/category.py backend/app/schemas/transaction.py \
  backend/app/services/categories.py backend/app/api/v1/categories.py \
  backend/app/api/v1/transactions.py backend/alembic/versions/0003_transaction_essential_tag.py \
  backend/tests/conftest.py backend/tests/test_categories_api.py \
  backend/tests/test_category_schemas.py backend/tests/test_transactions_api.py \
  backend/tests/test_summary_api.py
git commit -m "refactor: move essential/discretionary tag from category to transaction"
```

**Manual click-through checkpoint:** log in to the deployed app (or local `flutter build web` + backend), create an expense transaction, confirm the app doesn't yet show an essential/discretionary field (that's Task 6) but the backend accepts/rejects correctly if you hit the API directly (e.g. via the FastAPI `/docs` page) — this is a backend-only change so far, no frontend click-through needed yet, but worth confirming the deployed backend didn't break existing transaction creation from the app before continuing. If you don't have a way to redeploy/test this in isolation, it's fine to fold this checkpoint into Task 6's click-through instead — note that decision if you skip it here.

---

## Task 2: Budget suggestion algorithm (pure math module)

**Files:**
- Create: `backend/app/services/budget_engine.py`
- Test: `backend/tests/test_budget_engine.py`

**Interfaces:**
- Consumes: nothing (pure function, no DB, no ORM).
- Produces: `compute_suggested_amount(monthly_totals: list[Decimal]) -> Decimal`. Task 4/5 call this with 3 `Decimal` totals (oldest to newest) obtained from the database and get back a single quantized `Decimal` suggestion. Raises `ValueError` if not given exactly 3 totals.

This module has no I/O specifically so its math can be unit tested in isolation, matching `Planning/03_testing_strategy.md`'s "Unit tests: Budget engine math" requirement.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_budget_engine.py`:

```python
from decimal import Decimal

import pytest

from app.services.budget_engine import compute_suggested_amount


def test_weighted_average_with_no_outlier():
    # 3:2:1 weighting: (3*90 + 2*60 + 1*30) / 6 = (270+120+30)/6 = 420/6 = 70.00
    result = compute_suggested_amount([Decimal("30.00"), Decimal("60.00"), Decimal("90.00")])
    assert result == Decimal("70.00")


def test_outlier_in_newest_month_is_trimmed():
    # median of [30, 40, 200] is 40; 200 > 2*40=80, so newest (200) is trimmed.
    # Remaining: oldest=30, middle=40, weighted 2:1 (more recent=middle):
    # (2*40 + 1*30)/3 = (80+30)/3 = 110/3 = 36.666... -> 36.67
    result = compute_suggested_amount([Decimal("30.00"), Decimal("40.00"), Decimal("200.00")])
    assert result == Decimal("36.67")


def test_outlier_in_oldest_month_is_trimmed():
    # median of [300, 40, 50] sorted [40,50,300] is 50; 300>100, so oldest (300) is trimmed.
    # Remaining: middle=40, newest=50, weighted 2:1 (newest=2, middle=1):
    # (2*50 + 1*40)/3 = (100+40)/3 = 140/3 = 46.666... -> 46.67
    result = compute_suggested_amount([Decimal("300.00"), Decimal("40.00"), Decimal("50.00")])
    assert result == Decimal("46.67")


def test_outlier_in_middle_month_is_trimmed():
    # median of [30, 300, 50] sorted [30,50,300] is 50; 300>100, so middle (300) is trimmed.
    # Remaining: oldest=30, newest=50, weighted 2:1 (newest=2, oldest=1):
    # (2*50 + 1*30)/3 = (100+30)/3 = 130/3 = 43.333... -> 43.33
    result = compute_suggested_amount([Decimal("30.00"), Decimal("300.00"), Decimal("50.00")])
    assert result == Decimal("43.33")


def test_zero_months_do_not_trigger_outlier_trim():
    # Two zero months and one spending month: the median-is-zero guard stops
    # this being treated as ">2x zero" (which would be true of any positive
    # number and would make the rule fire constantly for sparse data).
    # (3*100 + 2*0 + 1*0)/6 = 300/6 = 50.00
    result = compute_suggested_amount([Decimal("0.00"), Decimal("0.00"), Decimal("100.00")])
    assert result == Decimal("50.00")


def test_requires_exactly_three_totals():
    with pytest.raises(ValueError):
        compute_suggested_amount([Decimal("10.00"), Decimal("20.00")])
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `cd backend && python -m pytest tests/test_budget_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.budget_engine'`.

- [ ] **Step 3: Implement `budget_engine.py`**

Create `backend/app/services/budget_engine.py`:

```python
"""Pure budget-suggestion math: 3-month weighted average with outlier trimming.

No I/O, no ORM -- takes plain Decimal inputs so it can be unit tested in
isolation from the database. Eligibility (whether a line even qualifies for
a suggestion) is a separate, DB-touching concern that lives in
app.services.budget; this module always computes a number from whatever 3
totals it's given.
"""
from decimal import ROUND_HALF_UP, Decimal

_OUTLIER_MULTIPLIER = Decimal("2")
_TWO_PLACES = Decimal("0.01")


def compute_suggested_amount(monthly_totals: list[Decimal]) -> Decimal:
    """Compute a suggested budget amount from 3 months of category-tag totals.

    `monthly_totals` must have exactly 3 entries, ordered oldest to newest
    (e.g. [June, July, August] if the current month is September).

    Applies the median-deviation outlier rule: if the highest of the 3
    months is more than 2x the median of the other two, it's dropped and
    the remaining 2 months are averaged, weighted 2:1 (more recent :
    older). Otherwise, all 3 months are averaged weighted 3:2:1 (newest :
    middle : oldest).
    """
    if len(monthly_totals) != 3:
        raise ValueError("compute_suggested_amount requires exactly 3 monthly totals")

    oldest, middle, newest = monthly_totals
    highest = max(monthly_totals)
    median = sorted(monthly_totals)[1]

    # median == 0 guard: without it, any nonzero month would be treated as
    # "more than 2x zero" and get trimmed as an outlier whenever two of the
    # three months have no spending in this category-tag -- which is a
    # normal cold-data pattern, not an outlier.
    if median > 0 and highest > median * _OUTLIER_MULTIPLIER:
        if highest == oldest:
            remaining_newer, remaining_older = newest, middle
        elif highest == middle:
            remaining_newer, remaining_older = newest, oldest
        else:
            remaining_newer, remaining_older = middle, oldest
        raw = (Decimal("2") * remaining_newer + Decimal("1") * remaining_older) / Decimal("3")
    else:
        raw = (Decimal("3") * newest + Decimal("2") * middle + Decimal("1") * oldest) / Decimal("6")

    return raw.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_budget_engine.py -v`
Expected: PASS, all 6 tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/budget_engine.py backend/tests/test_budget_engine.py
git commit -m "feat: add budget suggestion algorithm (3-month weighted average with outlier trimming)"
```

---

## Task 3: `income_targets` and `budgets` tables + manual-set endpoints

**Files:**
- Create: `backend/app/models/income_target.py`
- Create: `backend/app/models/budget.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0004_income_targets_and_budgets.py`
- Create: `backend/app/schemas/budget.py`
- Create: `backend/app/services/budget.py`
- Create: `backend/app/api/v1/budget.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/test_budget_api.py`

**Interfaces:**
- Consumes: nothing from Task 2 yet (that's Task 4).
- Produces: `budget_service.get_income_target(db, user_id) -> IncomeTarget | None`, `budget_service.set_income_target(db, user_id, payload: IncomeTargetSet) -> IncomeTarget`, `budget_service.get_budget_line(db, user_id, category_id, is_essential) -> Budget | None`, `budget_service.set_budget_line(db, user_id, payload: BudgetLineSet) -> Budget`. Models `IncomeTarget`, `Budget`, `BudgetSource` (enum: `COMPUTED`, `MANUAL`). Schemas `IncomeTargetSet`, `IncomeTargetRead`, `BudgetLineSet`, `BudgetLineWriteRead`. Router `PUT /api/v1/budget/income-target`, `PUT /api/v1/budget/lines`. Tasks 4 and 5 build on this router file and these service functions.

- [ ] **Step 1: Create the `IncomeTarget` model**

Create `backend/app/models/income_target.py`:

```python
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IncomeTarget(Base):
    __tablename__ = "income_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Create the `Budget` model**

Create `backend/app/models/budget.py`:

```python
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BudgetSource(str, enum.Enum):
    COMPUTED = "computed"
    MANUAL = "manual"


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "is_essential", name="uq_budgets_user_category_essential"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    is_essential: Mapped[bool] = mapped_column(Boolean, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[BudgetSource] = mapped_column(
        Enum(BudgetSource, name="budget_source", values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Export the new models**

Edit `backend/app/models/__init__.py`:

```python
from app.models.budget import Budget, BudgetSource
from app.models.category import Category, CategoryType
from app.models.income_target import IncomeTarget
from app.models.transaction import Transaction, TransactionType

__all__ = [
    "Budget",
    "BudgetSource",
    "Category",
    "CategoryType",
    "IncomeTarget",
    "Transaction",
    "TransactionType",
]
```

- [ ] **Step 4: Create the migration**

Create `backend/alembic/versions/0004_income_targets_and_budgets.py`:

```python
"""add income_targets and budgets tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-17
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "income_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_income_targets_user_id", "income_targets", ["user_id"])

    budget_source = sa.Enum("computed", "manual", name="budget_source")
    budget_source.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("is_essential", sa.Boolean(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", budget_source, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "category_id", "is_essential", name="uq_budgets_user_category_essential"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")
    sa.Enum(name="budget_source").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_income_targets_user_id", table_name="income_targets")
    op.drop_table("income_targets")
```

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/test_budget_api.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt

from app.core.config import get_settings
from app.services import budget as budget_service


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.supabase_jwt_aud,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_income_target_requires_auth(client):
    response = client.put("/api/v1/budget/income-target", json={"amount": "3000.00"})
    assert response.status_code == 401


def test_set_income_target_creates_then_updates(client, auth_headers):
    create_response = client.put(
        "/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers
    )
    assert create_response.status_code == 200
    assert create_response.json()["amount"] == "3000.00"

    update_response = client.put(
        "/api/v1/budget/income-target", json={"amount": "3200.00"}, headers=auth_headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == "3200.00"


def test_income_target_rejects_non_positive_amount(client, auth_headers):
    response = client.put("/api/v1/budget/income-target", json={"amount": "0.00"}, headers=auth_headers)
    assert response.status_code == 422


def test_income_target_isolated_between_users(client, auth_headers, user_id, other_user_id, db):
    client.put("/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers)

    assert budget_service.get_income_target(db, other_user_id) is None
    own_target = budget_service.get_income_target(db, user_id)
    assert own_target is not None
    assert own_target.amount == Decimal("3000.00")


def test_set_budget_line_requires_auth(client, seeded_category):
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
    )
    assert response.status_code == 401


def test_set_budget_line_creates_then_updates_as_manual(client, auth_headers, seeded_category):
    create_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["amount"] == "300.00"
    assert body["source"] == "manual"

    update_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "350.00"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == "350.00"


def test_set_budget_line_essential_and_discretionary_are_independent_lines(client, auth_headers, seeded_category):
    essential_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )
    discretionary_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": False, "amount": "100.00"},
        headers=auth_headers,
    )
    assert essential_response.json()["amount"] == "300.00"
    assert discretionary_response.json()["amount"] == "100.00"


def test_set_budget_line_rejects_income_category(client, auth_headers, seeded_income_category):
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_income_category.id), "is_essential": True, "amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_set_budget_line_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(other_user_category.id), "is_essential": True, "amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_set_budget_line_rejects_archived_category(client, auth_headers, seeded_category):
    client.patch(
        f"/api/v1/categories/{seeded_category.id}",
        json={"is_archived": True},
        headers=auth_headers,
    )
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 404
```

- [ ] **Step 6: Run the tests and see them fail**

Run: `cd backend && python -m pytest tests/test_budget_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.budget'` (and the route doesn't exist yet either).

- [ ] **Step 7: Create the budget schemas**

Create `backend/app/schemas/budget.py`:

```python
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
```

`_validate_amount` is reused from `app.schemas.transaction` (Task 1) rather than duplicated — same positive/2-decimal-places rule applies to budget amounts as to transaction amounts.

- [ ] **Step 8: Create the budget service**

Create `backend/app/services/budget.py`:

```python
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
```

- [ ] **Step 9: Create the budget router**

Create `backend/app/api/v1/budget.py`:

```python
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
```

- [ ] **Step 10: Register the router**

Edit `backend/app/api/v1/router.py`:

```python
from fastapi import APIRouter

from app.api.v1 import budget, categories, health, summary, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(summary.router)
api_router.include_router(budget.router)
```

- [ ] **Step 11: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_budget_api.py -v`
Expected: PASS, all tests green.

- [ ] **Step 12: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add backend/app/models/income_target.py backend/app/models/budget.py backend/app/models/__init__.py \
  backend/alembic/versions/0004_income_targets_and_budgets.py backend/app/schemas/budget.py \
  backend/app/services/budget.py backend/app/api/v1/budget.py backend/app/api/v1/router.py \
  backend/tests/test_budget_api.py
git commit -m "feat: add income_targets and budgets tables with manual-set endpoints"
```

---

## Task 4: Eligibility, suggestions, and accept-suggestion

**Files:**
- Modify: `backend/app/services/budget.py`
- Modify: `backend/app/schemas/budget.py`
- Modify: `backend/app/api/v1/budget.py`
- Create: `backend/tests/test_budget_suggestions_api.py`

**Interfaces:**
- Consumes: `compute_suggested_amount` (Task 2), `Budget`/`BudgetSource`/`get_budget_line` (Task 3), `categories_service.list_categories` (existing).
- Produces: `budget_service.list_suggestions(db, user_id) -> list[SuggestionItem]`, `budget_service.accept_suggestion(db, user_id, category_id, is_essential) -> Budget | None` (`None` means ineligible). Router `GET /api/v1/budget/suggestions`, `POST /api/v1/budget/lines/accept-suggestion`. Task 5's aggregate endpoint reuses the same eligibility helpers added here (`_three_preceding_months`, `_monthly_totals_for_line`, `is_eligible_for_suggestion`).

A month's transaction total for a `(category_id, is_essential)` pair is exactly `Decimal("0.00")` if and only if there were no matching transactions that month — transaction amounts are always positive (enforced by `_validate_amount` since M1), so a nonzero sum implies at least one transaction and a zero sum implies none. Eligibility can therefore be checked from the totals alone, with no separate `COUNT` query.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_budget_suggestions_api.py`:

```python
from datetime import date


def _three_months_ago_bounds(today: date) -> list[tuple[int, int]]:
    """Return (year, month) for the 3 calendar months before today's month, oldest first.

    Test-only helper: since eligibility is defined relative to the real
    wall-clock date (no `today` override exists in the API, matching how
    summary.py's month defaulting also uses date.today() directly), tests
    compute scenario dates relative to whenever the suite actually runs.
    """
    months = []
    year, month = today.year, today.month
    for _ in range(3):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        months.append((year, month))
    return list(reversed(months))


def _create_expense(client, headers, category_id, amount, year, month, is_essential):
    return client.post(
        "/api/v1/transactions",
        json={
            "category_id": category_id,
            "type": "expense",
            "amount": amount,
            "occurred_on": f"{year:04d}-{month:02d}-15",
            "is_essential": is_essential,
        },
        headers=headers,
    )


def test_line_with_three_months_of_data_is_eligible_and_suggests_weighted_average(client, auth_headers, seeded_category):
    months = _three_months_ago_bounds(date.today())
    amounts = ["30.00", "60.00", "90.00"]
    for (year, month), amount in zip(months, amounts):
        response = _create_expense(client, auth_headers, str(seeded_category.id), amount, year, month, True)
        assert response.status_code == 201

    suggestions_response = client.get("/api/v1/budget/suggestions", headers=auth_headers)
    assert suggestions_response.status_code == 200
    matching = [
        item for item in suggestions_response.json()
        if item["category_id"] == str(seeded_category.id) and item["is_essential"] is True
    ]
    assert len(matching) == 1
    # 3:2:1 weighting: (3*90 + 2*60 + 1*30) / 6 = 70.00
    assert matching[0]["suggested_amount"] == "70.00"


def test_line_with_gap_month_is_not_eligible(client, auth_headers, seeded_category):
    months = _three_months_ago_bounds(date.today())
    # Only the two most recent of the 3 months have data -- the oldest is missing.
    for (year, month) in months[1:]:
        response = _create_expense(client, auth_headers, str(seeded_category.id), "50.00", year, month, True)
        assert response.status_code == 201

    suggestions_response = client.get("/api/v1/budget/suggestions", headers=auth_headers)
    assert suggestions_response.status_code == 200
    matching = [
        item for item in suggestions_response.json()
        if item["category_id"] == str(seeded_category.id) and item["is_essential"] is True
    ]
    assert matching == []


def test_essential_and_discretionary_lines_are_independently_eligible(client, auth_headers, seeded_category):
    """3 months of essential-only spending shouldn't make the discretionary line of the same category eligible."""
    months = _three_months_ago_bounds(date.today())
    for (year, month) in months:
        _create_expense(client, auth_headers, str(seeded_category.id), "40.00", year, month, True)

    suggestions_response = client.get("/api/v1/budget/suggestions", headers=auth_headers)
    tags = {
        (item["category_id"], item["is_essential"])
        for item in suggestions_response.json()
        if item["category_id"] == str(seeded_category.id)
    }
    assert tags == {(str(seeded_category.id), True)}


def test_accept_suggestion_persists_as_computed(client, auth_headers, seeded_category):
    months = _three_months_ago_bounds(date.today())
    for (year, month) in months:
        _create_expense(client, auth_headers, str(seeded_category.id), "40.00", year, month, False)

    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_category.id), "is_essential": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == "40.00"
    assert body["source"] == "computed"


def test_accept_suggestion_rejects_ineligible_line(client, auth_headers, seeded_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_category.id), "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_accept_suggestion_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(other_user_category.id), "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_accept_suggestion_rejects_income_category(client, auth_headers, seeded_income_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_income_category.id), "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_suggestions_requires_auth(client):
    response = client.get("/api/v1/budget/suggestions")
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `cd backend && python -m pytest tests/test_budget_suggestions_api.py -v`
Expected: FAIL — 404s (routes don't exist yet).

- [ ] **Step 3: Add `SuggestionItem` and `AcceptSuggestionRequest` schemas**

Edit `backend/app/schemas/budget.py`, adding to the end of the file:

```python


class AcceptSuggestionRequest(BaseModel):
    category_id: uuid.UUID
    is_essential: bool


class SuggestionItem(BaseModel):
    category_id: uuid.UUID
    is_essential: bool
    suggested_amount: Decimal
```

- [ ] **Step 4: Add eligibility, suggestion-listing, and accept-suggestion to the service**

Edit `backend/app/services/budget.py`, adding these imports at the top:

```python
import calendar
from datetime import date
```

and adding these functions to the end of the file:

```python
def _three_preceding_months(today: date) -> list[tuple[date, date]]:
    """Return (start, end) bounds for the 3 calendar months before `today`'s month, oldest first."""
    bounds = []
    year, month = today.year, today.month
    for _ in range(3):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        last_day = calendar.monthrange(year, month)[1]
        bounds.append((date(year, month, 1), date(year, month, last_day)))
    return list(reversed(bounds))


def _monthly_totals_for_line(
    db: Session, user_id: uuid.UUID, category_id: uuid.UUID, is_essential: bool, today: date
) -> list[Decimal]:
    totals = []
    for start, end in _three_preceding_months(today):
        stmt = select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.is_essential == is_essential,
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
```

Also add these imports to the top of `backend/app/services/budget.py` (alongside the existing `from app.models import ...` line) and the `SuggestionItem` schema import:

```python
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Budget, BudgetSource, CategoryType, IncomeTarget, Transaction
from app.schemas.budget import BudgetLineSet, IncomeTargetSet, SuggestionItem
from app.services import categories as categories_service
from app.services.budget_engine import compute_suggested_amount
```

The complete top-of-file imports for `backend/app/services/budget.py` after this step:

```python
import calendar
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, BudgetSource, CategoryType, IncomeTarget, Transaction
from app.schemas.budget import BudgetLineSet, IncomeTargetSet, SuggestionItem
from app.services import categories as categories_service
from app.services.budget_engine import compute_suggested_amount
```

- [ ] **Step 5: Add the router endpoints**

Edit `backend/app/api/v1/budget.py`, updating the import line and adding two endpoints:

```python
from app.schemas.budget import (
    AcceptSuggestionRequest,
    BudgetLineSet,
    BudgetLineWriteRead,
    IncomeTargetRead,
    IncomeTargetSet,
    SuggestionItem,
)
```

Append to the end of the file:

```python


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
```

- [ ] **Step 6: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_budget_suggestions_api.py -v`
Expected: PASS, all tests green.

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/budget.py backend/app/schemas/budget.py backend/app/api/v1/budget.py \
  backend/tests/test_budget_suggestions_api.py
git commit -m "feat: add budget suggestion listing and accept-suggestion endpoints"
```

---

## Task 5: `GET /api/v1/budget` aggregate endpoint

**Files:**
- Create: `backend/app/services/date_utils.py`
- Test: `backend/tests/test_date_utils.py`
- Modify: `backend/app/services/summary.py`
- Modify: `backend/app/schemas/budget.py`
- Modify: `backend/app/services/budget.py`
- Modify: `backend/app/api/v1/budget.py`
- Create: `backend/tests/test_budget_state_api.py`

**Interfaces:**
- Consumes: `_monthly_totals_for_line`, `is_eligible_for_suggestion` (Task 4); `categories_service.list_categories` (existing).
- Produces: `month_bounds(month: str) -> tuple[date, date]` (shared, replaces the private duplicate in `summary.py`), `budget_service.get_budget_state(db, user_id, month) -> BudgetState`, `GET /api/v1/budget?month=YYYY-MM`. This is the last backend task — Task 7 (frontend) consumes this endpoint's exact response shape.

`summary.py` already has a private `_month_bounds` doing the same single-month date math this endpoint needs. Rather than a third copy, this task extracts it into a small shared module and updates `summary.py` to use it — a small, justified DRY refactor since the same logic is now needed in two service files.

- [ ] **Step 1: Write the failing test for the shared date helper**

Create `backend/tests/test_date_utils.py`:

```python
from datetime import date

from app.services.date_utils import month_bounds


def test_month_bounds_returns_first_and_last_day():
    start, end = month_bounds("2026-02")
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_month_bounds_handles_31_day_month():
    start, end = month_bounds("2026-01")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)
```

- [ ] **Step 2: Run it and see it fail**

Run: `cd backend && python -m pytest tests/test_date_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.date_utils'`.

- [ ] **Step 3: Create `date_utils.py` and update `summary.py` to use it**

Create `backend/app/services/date_utils.py`:

```python
import calendar
from datetime import date


def month_bounds(month: str) -> tuple[date, date]:
    """Return (start, end) dates for a 'YYYY-MM' string, inclusive."""
    year_str, month_str = month.split("-")
    year, month_num = int(year_str), int(month_str)
    start = date(year, month_num, 1)
    last_day = calendar.monthrange(year, month_num)[1]
    end = date(year, month_num, last_day)
    return start, end
```

Edit `backend/app/services/summary.py` so it reads:

```python
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction, TransactionType
from app.schemas.summary import CategoryBreakdownItem, MonthlySummary
from app.services.date_utils import month_bounds


def get_monthly_summary(db: Session, user_id: uuid.UUID, month: str) -> MonthlySummary:
    start, end = month_bounds(month)

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
```

(This removes the old private `_month_bounds` function, and the now-unused `import calendar` / `from datetime import date` lines, from `summary.py`.)

- [ ] **Step 4: Run the date_utils test and the summary suite**

Run: `cd backend && python -m pytest tests/test_date_utils.py tests/test_summary_api.py -v`
Expected: PASS — `test_date_utils.py` is new and green; `test_summary_api.py` is unchanged behavior, still green.

- [ ] **Step 5: Write the failing tests for `GET /api/v1/budget`**

Create `backend/tests/test_budget_state_api.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.supabase_jwt_aud,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_budget_requires_auth(client):
    response = client.get("/api/v1/budget")
    assert response.status_code == 401


def test_budget_empty_state_has_no_income_target_and_no_lines(client, auth_headers):
    response = client.get("/api/v1/budget?month=2020-01", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["income_target"] is None
    assert body["projected_net"] is None
    assert body["lines"] == []
    assert body["actual_income_this_month"] == "0.00"
    assert body["actual_net_so_far"] == "0.00"


def test_budget_rejects_invalid_month(client, auth_headers):
    response = client.get("/api/v1/budget?month=2026-13", headers=auth_headers)
    assert response.status_code == 422


def test_budget_line_appears_from_history_without_a_saved_budget(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "40.00",
            "occurred_on": "2026-09-05",
            "is_essential": True,
        },
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    assert response.status_code == 200
    lines = response.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["category_id"] == str(seeded_category.id)
    assert lines[0]["is_essential"] is True
    assert lines[0]["budget_amount"] is None
    assert lines[0]["source"] is None
    assert lines[0]["actual_this_month"] == "40.00"


def test_budget_totals_and_projected_net(client, auth_headers, seeded_category):
    client.put("/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers)
    client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )
    client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": False, "amount": "100.00"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    body = response.json()
    assert body["income_target"] == "3000.00"
    assert body["essentials_budget_total"] == "300.00"
    assert body["discretionary_budget_total"] == "100.00"
    assert body["projected_net"] == "2600.00"


def test_budget_actual_net_so_far(client, auth_headers, seeded_category, seeded_income_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_income_category.id), "type": "income", "amount": "1000.00", "occurred_on": "2026-09-01"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "150.00", "occurred_on": "2026-09-05", "is_essential": True},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "50.00", "occurred_on": "2026-09-10", "is_essential": False},
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    body = response.json()
    assert body["actual_income_this_month"] == "1000.00"
    assert body["essentials_actual_total"] == "150.00"
    assert body["discretionary_actual_total"] == "50.00"
    assert body["actual_net_so_far"] == "800.00"


def test_budget_month_query_param_scopes_actuals_but_not_line_presence(client, auth_headers, seeded_category):
    """A line's presence depends on all-time history; only its actual_this_month is month-scoped."""
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "40.00", "occurred_on": "2026-08-05", "is_essential": True},
        headers=auth_headers,
    )

    september_response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    september_lines = september_response.json()["lines"]
    assert len(september_lines) == 1
    assert september_lines[0]["actual_this_month"] == "0.00"

    august_response = client.get("/api/v1/budget?month=2026-08", headers=auth_headers)
    august_lines = august_response.json()["lines"]
    assert len(august_lines) == 1
    assert august_lines[0]["actual_this_month"] == "40.00"


def test_budget_is_isolated_between_users(client, auth_headers, seeded_category, other_user_id):
    client.put("/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers)
    client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )

    other_headers = _auth_headers_for(other_user_id)
    response = client.get("/api/v1/budget", headers=other_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["income_target"] is None
    assert body["lines"] == []
```

- [ ] **Step 6: Run the tests and see them fail**

Run: `cd backend && python -m pytest tests/test_budget_state_api.py -v`
Expected: FAIL — 404 (route doesn't exist) / `AttributeError` (schema doesn't exist).

- [ ] **Step 7: Add `BudgetLineRead` and `BudgetState` schemas**

Edit `backend/app/schemas/budget.py`, adding to the end of the file:

```python


class BudgetLineRead(BaseModel):
    category_id: uuid.UUID
    category_name: str
    is_essential: bool
    budget_amount: Decimal | None
    source: BudgetSource | None
    eligible_for_suggestion: bool
    actual_this_month: Decimal


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
```

`projected_net` is nullable: with no income target set, there's no meaningful "plan" to project a net for, so the field is `None` rather than a misleading negative number derived from a zero that was never the user's real income.

- [ ] **Step 8: Add `get_budget_state` to the service**

Edit `backend/app/services/budget.py`: update the schema import line to include the new schemas, and add `get_budget_state` to the end of the file.

Change:
```python
from app.schemas.budget import BudgetLineSet, IncomeTargetSet, SuggestionItem
```
to:
```python
from app.schemas.budget import BudgetLineRead, BudgetLineSet, BudgetState, IncomeTargetSet, SuggestionItem
```

Add `Transaction, TransactionType` to the existing `from app.models import ...` line (it currently imports `Budget, BudgetSource, CategoryType, IncomeTarget, Transaction` — add `TransactionType`):
```python
from app.models import Budget, BudgetSource, CategoryType, IncomeTarget, Transaction, TransactionType
```

Add the `month_bounds` import:
```python
from app.services.date_utils import month_bounds
```

Append this function to the end of the file:

```python
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
    actual_net_so_far = actual_income_this_month - essentials_actual_total - discretionary_actual_total

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
```

- [ ] **Step 9: Add the router endpoint**

Edit `backend/app/api/v1/budget.py`: update imports and add the endpoint.

Add to the top imports:
```python
from datetime import date

from fastapi import Query
```

(`Query` joins the existing `from fastapi import APIRouter, Depends, HTTPException, status` — combine into one import line: `from fastapi import APIRouter, Depends, HTTPException, Query, status`.)

Update the schema import line to add `BudgetState`:
```python
from app.schemas.budget import (
    AcceptSuggestionRequest,
    BudgetLineSet,
    BudgetLineWriteRead,
    BudgetState,
    IncomeTargetRead,
    IncomeTargetSet,
    SuggestionItem,
)
```

Append to the end of the file:

```python


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
```

- [ ] **Step 10: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_budget_state_api.py -v`
Expected: PASS, all tests green.

- [ ] **Step 11: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS, all tests green (should be 49 + new tests from Tasks 2-5 by this point).

- [ ] **Step 12: Commit**

```bash
git add backend/app/services/date_utils.py backend/tests/test_date_utils.py backend/app/services/summary.py \
  backend/app/schemas/budget.py backend/app/services/budget.py backend/app/api/v1/budget.py \
  backend/tests/test_budget_state_api.py
git commit -m "feat: add GET /api/v1/budget aggregate endpoint"
```

**Manual click-through checkpoint:** the backend side of the budget engine is now complete. Using the FastAPI `/docs` page (or `curl`) against the real deployed backend: log an expense transaction with `is_essential`, set an income target, set a manual budget line, hit `GET /api/v1/budget` and confirm the totals/projected-net/actual-net match by hand. This is the point to catch a wrong aggregation before building UI on top of it — the M1 Render `SUPABASE_URL` bug and the M2 dashboard staleness bug were both the kind of thing that only surfaces when you actually exercise the real deployed path, not just the test suite.

---

## Task 6: Frontend — move `is_essential` from Category to Transaction

**Files:**
- Modify: `frontend/money_tracker_app/lib/features/categories/models/category.dart`
- Modify: `frontend/money_tracker_app/lib/features/categories/providers/category_provider.dart`
- Modify: `frontend/money_tracker_app/lib/features/categories/screens/category_form_screen.dart`
- Modify: `frontend/money_tracker_app/lib/features/categories/screens/category_list_screen.dart`
- Modify: `frontend/money_tracker_app/lib/features/transactions/models/transaction.dart`
- Modify: `frontend/money_tracker_app/lib/features/transactions/screens/transaction_entry_screen.dart`
- Modify: `frontend/money_tracker_app/test/features/categories/category_form_screen_test.dart`
- Modify: `frontend/money_tracker_app/test/features/categories/category_list_screen_test.dart`
- Modify: `frontend/money_tracker_app/test/features/transactions/transaction_entry_screen_test.dart`
- Modify: `frontend/money_tracker_app/test/features/transactions/transaction_model_test.dart`

**Interfaces:**
- Consumes: the backend contract from Task 1 (`Category` no longer has `is_essential`; `Transaction`/`TransactionDraft` requires it for expense).
- Produces: `Category` model without `isEssential`; `TransactionDraft` with `isEssential`. Task 7 imports `Category`/`categoryListProvider` unchanged otherwise.

- [ ] **Step 1: Update the failing/soon-to-fail tests first**

Edit `frontend/money_tracker_app/test/features/categories/category_form_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/categories/screens/category_form_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel('plugins.flutter.io/shared_preferences');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(url: 'http://localhost:54321', publishableKey: 'test-anon-key');
  });

  testWidgets('CategoryFormScreen has no essential toggle -- that tag now lives on transactions',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: CategoryFormScreen())),
    );

    expect(find.byKey(const Key('category_essential_toggle')), findsNothing);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.byKey(const Key('category_essential_toggle')), findsNothing);
  });
}
```

Edit `frontend/money_tracker_app/test/features/categories/category_list_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/core/api_client.dart';
import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/categories/screens/category_list_screen.dart';

/// A CategoryController stand-in whose `archive` always fails, so the test
/// can assert the failure surfaces to the user instead of vanishing silently.
class _FailingCategoryController extends CategoryController {
  _FailingCategoryController(super.apiClient, super.ref);

  @override
  Future<void> archive(String categoryId) async {
    state = const AsyncLoading();
    state = AsyncError<void>(Exception('network error'), StackTrace.empty);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel('plugins.flutter.io/shared_preferences');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(url: 'http://localhost:54321', publishableKey: 'test-anon-key');
  });

  testWidgets('CategoryListScreen renders fetched categories without an essential toggle',
      (tester) async {
    final categories = [
      Category(id: '1', name: 'Food', type: 'expense', isArchived: false),
      Category(id: '2', name: 'Salary', type: 'income', isArchived: false),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => categories)],
        child: const MaterialApp(home: CategoryListScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Food'), findsOneWidget);
    expect(find.text('Salary'), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle_1')), findsNothing);
    expect(find.byKey(const Key('add_category_button')), findsOneWidget);
  });

  testWidgets(
      'CategoryListScreen shows a SnackBar when a category mutation fails',
      (tester) async {
    final categories = [
      Category(id: '1', name: 'Food', type: 'expense', isArchived: false),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          categoryListProvider.overrideWith((ref) async => categories),
          categoryControllerProvider.overrideWith(
            (ref) => _FailingCategoryController(ref.watch(apiClientProvider), ref),
          ),
        ],
        child: const MaterialApp(home: CategoryListScreen()),
      ),
    );
    await tester.pump();

    await tester.tap(find.byKey(const Key('archive_button_1')));
    await tester.pump();

    expect(find.textContaining('Failed to update category'), findsOneWidget);
  });
}
```

Edit `frontend/money_tracker_app/test/features/transactions/transaction_entry_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/transactions/screens/transaction_entry_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel('plugins.flutter.io/shared_preferences');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(url: 'http://localhost:54321', publishableKey: 'test-anon-key');
  });

  final fakeCategories = [
    Category(id: '1', name: 'Food', type: 'expense', isArchived: false),
    Category(id: '2', name: 'Salary', type: 'income', isArchived: false),
  ];

  testWidgets('TransactionEntryScreen exposes exactly the required fields',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => fakeCategories)],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('amount_field')), findsOneWidget);
    expect(find.byKey(const Key('type_toggle')), findsOneWidget);
    expect(find.byKey(const Key('category_dropdown')), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle')), findsOneWidget);
    expect(find.byKey(const Key('date_field')), findsOneWidget);
    expect(find.byKey(const Key('note_field')), findsOneWidget);
    expect(find.byKey(const Key('submit_button')), findsOneWidget);
  });

  testWidgets('Essential/Discretionary toggle only shows for expense type',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => fakeCategories)],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('essential_toggle')), findsOneWidget);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.byKey(const Key('essential_toggle')), findsNothing);
  });

  testWidgets('Category dropdown only shows categories matching the selected type',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => fakeCategories)],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Food'), findsOneWidget);
    expect(find.text('Salary'), findsNothing);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.text('Salary'), findsOneWidget);
  });

  testWidgets(
      'Submitting with no category available for the selected type shows feedback instead of doing nothing',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [categoryListProvider.overrideWith((ref) async => <Category>[])],
        child: const MaterialApp(home: TransactionEntryScreen()),
      ),
    );
    await tester.pump();

    await tester.tap(find.byKey(const Key('submit_button')));
    await tester.pump();

    expect(find.text('No category available for this type'), findsOneWidget);
  });
}
```

Edit `frontend/money_tracker_app/test/features/transactions/transaction_model_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:money_tracker_app/features/transactions/models/transaction.dart';

void main() {
  test('TransactionDraft serializes amount as a decimal string, not a double', () {
    final draft = TransactionDraft(
      categoryId: '11111111-1111-1111-1111-111111111111',
      type: 'expense',
      amount: '19.99',
      occurredOn: '2026-09-01',
      note: 'Lunch',
    );

    final json = draft.toJson();

    expect(json['amount'], '19.99');
    expect(json['amount'], isA<String>());
  });

  test('TransactionDraft includes is_essential when provided', () {
    final draft = TransactionDraft(
      categoryId: '11111111-1111-1111-1111-111111111111',
      type: 'expense',
      amount: '19.99',
      occurredOn: '2026-09-01',
      isEssential: false,
    );

    expect(draft.toJson()['is_essential'], false);
  });

  test('TransactionDraft omits is_essential when null', () {
    final draft = TransactionDraft(
      categoryId: '11111111-1111-1111-1111-111111111111',
      type: 'income',
      amount: '1000.00',
      occurredOn: '2026-09-01',
    );

    expect(draft.toJson().containsKey('is_essential'), false);
  });
}
```

- [ ] **Step 2: Run the frontend tests and see the relevant ones fail**

Run: `cd frontend/money_tracker_app && flutter test`
Expected: FAIL — compile errors, since `Category`/`TransactionDraft` don't have the new shape yet.

- [ ] **Step 3: Update the `Category` model**

Edit `frontend/money_tracker_app/lib/features/categories/models/category.dart`:

```dart
class Category {
  Category({
    required this.id,
    required this.name,
    required this.type,
    required this.isArchived,
  });

  final String id;
  final String name;
  final String type;
  final bool isArchived;

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as String,
        name: json['name'] as String,
        type: json['type'] as String,
        isArchived: json['is_archived'] as bool,
      );
}
```

- [ ] **Step 4: Update the category provider**

Edit `frontend/money_tracker_app/lib/features/categories/providers/category_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';

import '../../../core/api_client.dart';
import '../models/category.dart';

final categoryListProvider = FutureProvider<List<Category>>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/categories');
  final data = response.data as List<dynamic>;
  return data.map((json) => Category.fromJson(json as Map<String, dynamic>)).toList();
});

final categoryControllerProvider =
    StateNotifierProvider<CategoryController, AsyncValue<void>>((ref) {
  return CategoryController(ref.watch(apiClientProvider), ref);
});

class CategoryController extends StateNotifier<AsyncValue<void>> {
  CategoryController(this._apiClient, this._ref) : super(const AsyncData(null));

  final ApiClient _apiClient;
  final Ref _ref;

  Future<void> create({required String name, required String type}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.post('/categories', data: {
        'name': name,
        'type': type,
      });
      _ref.invalidate(categoryListProvider);
    });
  }

  Future<void> archive(String categoryId) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.patch('/categories/$categoryId', data: {'is_archived': true});
      _ref.invalidate(categoryListProvider);
    });
  }
}
```

- [ ] **Step 5: Update the category form screen**

Edit `frontend/money_tracker_app/lib/features/categories/screens/category_form_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/category_provider.dart';

class CategoryFormScreen extends ConsumerStatefulWidget {
  const CategoryFormScreen({super.key});

  @override
  ConsumerState<CategoryFormScreen> createState() => _CategoryFormScreenState();
}

class _CategoryFormScreenState extends ConsumerState<CategoryFormScreen> {
  final _nameController = TextEditingController();
  String _type = 'expense';

  @override
  Widget build(BuildContext context) {
    final controllerState = ref.watch(categoryControllerProvider);

    ref.listen(categoryControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        Navigator.of(context).pop();
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('New category')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            TextField(
              key: const Key('category_name_field'),
              controller: _nameController,
              decoration: const InputDecoration(labelText: 'Name'),
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              key: const Key('category_type_toggle'),
              segments: const [
                ButtonSegment(value: 'expense', label: Text('Expense')),
                ButtonSegment(value: 'income', label: Text('Income')),
              ],
              selected: {_type},
              onSelectionChanged: (selection) => setState(() {
                _type = selection.first;
              }),
            ),
            const SizedBox(height: 24),
            if (controllerState.hasError)
              Text('Failed to save: ${controllerState.error}', style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              key: const Key('save_category_button'),
              onPressed: controllerState.isLoading ? null : _submit,
              child: controllerState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  void _submit() {
    ref.read(categoryControllerProvider.notifier).create(
          name: _nameController.text.trim(),
          type: _type,
        );
  }
}
```

- [ ] **Step 6: Update the category list screen**

Edit `frontend/money_tracker_app/lib/features/categories/screens/category_list_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/category.dart';
import '../providers/category_provider.dart';
import 'category_form_screen.dart';

class CategoryListScreen extends ConsumerWidget {
  const CategoryListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categoriesAsync = ref.watch(categoryListProvider);

    ref.listen(categoryControllerProvider, (previous, next) {
      if (next.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update category: ${next.error}')),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Categories')),
      body: categoriesAsync.when(
        data: (categories) => ListView(
          children: categories.map((category) => _CategoryTile(category: category)).toList(),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load categories: $error')),
      ),
      floatingActionButton: FloatingActionButton(
        key: const Key('add_category_button'),
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const CategoryFormScreen()),
        ),
        child: const Icon(Icons.add),
      ),
    );
  }
}

class _CategoryTile extends ConsumerWidget {
  const _CategoryTile({required this.category});

  final Category category;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListTile(
      title: Text(category.name),
      subtitle: Text(category.type),
      trailing: IconButton(
        key: Key('archive_button_${category.id}'),
        icon: const Icon(Icons.archive_outlined),
        onPressed: () => ref.read(categoryControllerProvider.notifier).archive(category.id),
      ),
    );
  }
}
```

- [ ] **Step 7: Update the `TransactionDraft` model**

Edit `frontend/money_tracker_app/lib/features/transactions/models/transaction.dart`:

```dart
class TransactionDraft {
  TransactionDraft({
    required this.categoryId,
    required this.type,
    required this.amount,
    required this.occurredOn,
    this.note,
    this.isEssential,
  });

  final String categoryId;
  final String type;
  final String amount;
  final String occurredOn;
  final String? note;
  final bool? isEssential;

  Map<String, dynamic> toJson() => {
        'category_id': categoryId,
        'type': type,
        'amount': amount,
        'occurred_on': occurredOn,
        if (note != null && note!.isNotEmpty) 'note': note,
        if (isEssential != null) 'is_essential': isEssential,
      };
}
```

- [ ] **Step 8: Add the essential/discretionary toggle to the transaction entry screen**

Edit `frontend/money_tracker_app/lib/features/transactions/screens/transaction_entry_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../categories/providers/category_provider.dart';
import '../models/transaction.dart';
import '../providers/transaction_provider.dart';

class TransactionEntryScreen extends ConsumerStatefulWidget {
  const TransactionEntryScreen({super.key});

  @override
  ConsumerState<TransactionEntryScreen> createState() => _TransactionEntryScreenState();
}

class _TransactionEntryScreenState extends ConsumerState<TransactionEntryScreen> {
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  String _type = 'expense';
  String? _categoryId;
  bool _isEssential = true;
  DateTime _occurredOn = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final entryState = ref.watch(transactionEntryControllerProvider);
    final categoriesAsync = ref.watch(categoryListProvider);

    ref.listen(transactionEntryControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Transaction saved')),
        );
        _amountController.clear();
        _noteController.clear();
        setState(() {
          _type = 'expense';
          _categoryId = null;
          _isEssential = true;
          _occurredOn = DateTime.now();
        });
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Add transaction')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            SegmentedButton<String>(
              key: const Key('type_toggle'),
              segments: const [
                ButtonSegment(value: 'expense', label: Text('Expense')),
                ButtonSegment(value: 'income', label: Text('Income')),
              ],
              selected: {_type},
              onSelectionChanged: (selection) => setState(() {
                _type = selection.first;
                _categoryId = null;
              }),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('amount_field'),
              controller: _amountController,
              decoration: const InputDecoration(labelText: 'Amount'),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 12),
            categoriesAsync.when(
              data: (categories) {
                final filtered = categories.where((c) => c.type == _type).toList();
                if (_categoryId == null && filtered.isNotEmpty) {
                  _categoryId = filtered.first.id;
                }
                return DropdownButton<String>(
                  key: const Key('category_dropdown'),
                  value: _categoryId,
                  items: filtered
                      .map((c) => DropdownMenuItem(value: c.id, child: Text(c.name)))
                      .toList(),
                  onChanged: (value) => setState(() => _categoryId = value),
                );
              },
              loading: () => const CircularProgressIndicator(key: Key('category_dropdown')),
              error: (error, _) =>
                  Text('Failed to load categories: $error', key: const Key('category_dropdown')),
            ),
            const SizedBox(height: 12),
            if (_type == 'expense')
              SegmentedButton<bool>(
                key: const Key('essential_toggle'),
                segments: const [
                  ButtonSegment(value: true, label: Text('Essential')),
                  ButtonSegment(value: false, label: Text('Discretionary')),
                ],
                selected: {_isEssential},
                onSelectionChanged: (selection) => setState(() => _isEssential = selection.first),
              ),
            const SizedBox(height: 12),
            InkWell(
              key: const Key('date_field'),
              onTap: _pickDate,
              child: InputDecorator(
                decoration: const InputDecoration(labelText: 'Date'),
                child: Text(
                  '${_occurredOn.year.toString().padLeft(4, '0')}-'
                  '${_occurredOn.month.toString().padLeft(2, '0')}-'
                  '${_occurredOn.day.toString().padLeft(2, '0')}',
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('note_field'),
              controller: _noteController,
              decoration: const InputDecoration(labelText: 'Note (optional)'),
            ),
            const SizedBox(height: 24),
            if (entryState.hasError)
              Text('Failed to save: ${entryState.error}', style: const TextStyle(color: Colors.red)),
            ElevatedButton(
              key: const Key('submit_button'),
              onPressed: entryState.isLoading ? null : _submit,
              child: entryState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Save transaction'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _occurredOn,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _occurredOn = picked);
    }
  }

  void _submit() {
    final categoryId = _categoryId;
    if (categoryId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No category available for this type')),
      );
      return;
    }
    final draft = TransactionDraft(
      categoryId: categoryId,
      type: _type,
      amount: _amountController.text,
      occurredOn: _occurredOn.toIso8601String().split('T').first,
      note: _noteController.text,
      isEssential: _type == 'expense' ? _isEssential : null,
    );
    ref.read(transactionEntryControllerProvider.notifier).submit(draft);
  }
}
```

- [ ] **Step 9: Run the frontend tests and see them pass**

Run: `cd frontend/money_tracker_app && flutter test`
Expected: PASS, all tests green.

- [ ] **Step 10: Run `flutter analyze`**

Run: `cd frontend/money_tracker_app && flutter analyze`
Expected: No issues found.

- [ ] **Step 11: Commit**

```bash
git add frontend/money_tracker_app/lib/features/categories frontend/money_tracker_app/lib/features/transactions \
  frontend/money_tracker_app/test/features/categories frontend/money_tracker_app/test/features/transactions
git commit -m "refactor: move essential/discretionary toggle from category form to transaction entry"
```

**Manual click-through checkpoint:** log in to the real app, add an expense transaction and confirm the Essential/Discretionary toggle appears and is required-feeling (defaults to Essential, switches to Discretionary), confirm it disappears for Income, confirm the category form no longer has an essential toggle, and confirm the category list no longer shows the essential switch. Check the transaction actually saved correctly by looking at the dashboard/summary afterward.

---

## Task 7: Frontend — Budget feature and navigation tab

**Files:**
- Create: `frontend/money_tracker_app/lib/features/budget/models/budget_state.dart`
- Create: `frontend/money_tracker_app/lib/features/budget/providers/budget_provider.dart`
- Create: `frontend/money_tracker_app/lib/features/budget/screens/budget_screen.dart`
- Modify: `frontend/money_tracker_app/lib/core/home_shell.dart`
- Create: `frontend/money_tracker_app/test/features/budget/budget_screen_test.dart`
- Modify: `frontend/money_tracker_app/test/core/home_shell_test.dart`

**Interfaces:**
- Consumes: `GET /api/v1/budget`, `PUT /api/v1/budget/income-target`, `PUT /api/v1/budget/lines`, `POST /api/v1/budget/lines/accept-suggestion`, `GET /api/v1/budget/suggestions` (Tasks 3-5's exact response shapes).
- Produces: `BudgetLine`, `BudgetSuggestion`, `BudgetState` models; `budgetProvider`, `budgetSuggestionsProvider`, `budgetControllerProvider`; `BudgetScreen`. This is the last task in the plan.

- [ ] **Step 1: Write the failing widget tests**

Create `frontend/money_tracker_app/test/features/budget/budget_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/core/api_client.dart';
import 'package:money_tracker_app/features/budget/models/budget_state.dart';
import 'package:money_tracker_app/features/budget/providers/budget_provider.dart';
import 'package:money_tracker_app/features/budget/screens/budget_screen.dart';

class _RecordingBudgetController extends BudgetController {
  _RecordingBudgetController(super.apiClient, super.ref);

  String? lastIncomeTargetAmount;
  String? lastLineCategoryId;
  bool? lastLineIsEssential;
  String? lastLineAmount;
  String? lastAcceptedCategoryId;
  bool? lastAcceptedIsEssential;

  @override
  Future<void> setIncomeTarget(String amount) async {
    lastIncomeTargetAmount = amount;
    state = const AsyncData(null);
  }

  @override
  Future<void> setLine({required String categoryId, required bool isEssential, required String amount}) async {
    lastLineCategoryId = categoryId;
    lastLineIsEssential = isEssential;
    lastLineAmount = amount;
    state = const AsyncData(null);
  }

  @override
  Future<void> acceptSuggestion({required String categoryId, required bool isEssential}) async {
    lastAcceptedCategoryId = categoryId;
    lastAcceptedIsEssential = isEssential;
    state = const AsyncData(null);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const sharedPreferencesChannel = MethodChannel('plugins.flutter.io/shared_preferences');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(sharedPreferencesChannel, (call) async {
    if (call.method == 'getAll') return <String, dynamic>{};
    return null;
  });

  setUpAll(() async {
    await Supabase.initialize(url: 'http://localhost:54321', publishableKey: 'test-anon-key');
  });

  final essentialLineWithBudget = BudgetLine(
    categoryId: '1',
    categoryName: 'Food',
    isEssential: true,
    budgetAmount: '300.00',
    source: 'manual',
    eligibleForSuggestion: false,
    actualThisMonth: '150.00',
  );

  final discretionaryLineColdStart = BudgetLine(
    categoryId: '1',
    categoryName: 'Food',
    isEssential: false,
    budgetAmount: null,
    source: null,
    eligibleForSuggestion: true,
    actualThisMonth: '40.00',
  );

  final state = BudgetState(
    incomeTarget: '3000.00',
    actualIncomeThisMonth: '1000.00',
    lines: [essentialLineWithBudget, discretionaryLineColdStart],
    essentialsBudgetTotal: '300.00',
    discretionaryBudgetTotal: '0.00',
    essentialsActualTotal: '150.00',
    discretionaryActualTotal: '40.00',
    projectedNet: '2700.00',
    actualNetSoFar: '810.00',
  );

  testWidgets('BudgetScreen renders totals, net figures, and lines', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Actual income: 1000.00'), findsOneWidget);
    expect(find.text('Projected net: 2700.00'), findsOneWidget);
    expect(find.text('Actual net so far: 810.00'), findsOneWidget);
    expect(find.textContaining('Food'), findsWidgets);
    expect(find.byKey(const Key('line_progress_1-true')), findsOneWidget);
    expect(find.byKey(const Key('line_amount_field_1-false')), findsOneWidget);
  });

  testWidgets('Saving a manual amount on a cold-start line calls setLine', (tester) async {
    late _RecordingBudgetController controller;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byKey(const Key('line_amount_field_1-false')), '120.00');
    await tester.tap(find.byKey(const Key('save_line_button_1-false')));
    await tester.pump();

    expect(controller.lastLineCategoryId, '1');
    expect(controller.lastLineIsEssential, false);
    expect(controller.lastLineAmount, '120.00');
  });

  testWidgets('Accept-suggestion button shows the suggested amount and triggers acceptSuggestion',
      (tester) async {
    late _RecordingBudgetController controller;
    final suggestion = BudgetSuggestion(categoryId: '1', isEssential: false, suggestedAmount: '55.00');

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => [suggestion]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Use suggestion: 55.00'), findsOneWidget);

    await tester.tap(find.byKey(const Key('accept_suggestion_button_1-false')));
    await tester.pump();

    expect(controller.lastAcceptedCategoryId, '1');
    expect(controller.lastAcceptedIsEssential, false);
  });

  testWidgets('Saving the income target calls setIncomeTarget', (tester) async {
    late _RecordingBudgetController controller;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          budgetProvider.overrideWith((ref) async => state),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
          budgetControllerProvider.overrideWith((ref) {
            controller = _RecordingBudgetController(ref.watch(apiClientProvider), ref);
            return controller;
          }),
        ],
        child: const MaterialApp(home: BudgetScreen()),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byKey(const Key('income_target_field')), '3500.00');
    await tester.tap(find.byKey(const Key('save_income_target_button')));
    await tester.pump();

    expect(controller.lastIncomeTargetAmount, '3500.00');
  });
}
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `cd frontend/money_tracker_app && flutter test test/features/budget/budget_screen_test.dart`
Expected: FAIL — the `budget` feature files don't exist yet.

- [ ] **Step 3: Create the budget models**

Create `frontend/money_tracker_app/lib/features/budget/models/budget_state.dart`:

```dart
class BudgetLine {
  BudgetLine({
    required this.categoryId,
    required this.categoryName,
    required this.isEssential,
    required this.budgetAmount,
    required this.source,
    required this.eligibleForSuggestion,
    required this.actualThisMonth,
  });

  final String categoryId;
  final String categoryName;
  final bool isEssential;
  final String? budgetAmount;
  final String? source;
  final bool eligibleForSuggestion;
  final String actualThisMonth;

  factory BudgetLine.fromJson(Map<String, dynamic> json) => BudgetLine(
        categoryId: json['category_id'] as String,
        categoryName: json['category_name'] as String,
        isEssential: json['is_essential'] as bool,
        budgetAmount: json['budget_amount'] as String?,
        source: json['source'] as String?,
        eligibleForSuggestion: json['eligible_for_suggestion'] as bool,
        actualThisMonth: json['actual_this_month'] as String,
      );
}

class BudgetState {
  BudgetState({
    required this.incomeTarget,
    required this.actualIncomeThisMonth,
    required this.lines,
    required this.essentialsBudgetTotal,
    required this.discretionaryBudgetTotal,
    required this.essentialsActualTotal,
    required this.discretionaryActualTotal,
    required this.projectedNet,
    required this.actualNetSoFar,
  });

  final String? incomeTarget;
  final String actualIncomeThisMonth;
  final List<BudgetLine> lines;
  final String essentialsBudgetTotal;
  final String discretionaryBudgetTotal;
  final String essentialsActualTotal;
  final String discretionaryActualTotal;
  final String? projectedNet;
  final String actualNetSoFar;

  factory BudgetState.fromJson(Map<String, dynamic> json) => BudgetState(
        incomeTarget: json['income_target'] as String?,
        actualIncomeThisMonth: json['actual_income_this_month'] as String,
        lines: (json['lines'] as List<dynamic>)
            .map((item) => BudgetLine.fromJson(item as Map<String, dynamic>))
            .toList(),
        essentialsBudgetTotal: json['essentials_budget_total'] as String,
        discretionaryBudgetTotal: json['discretionary_budget_total'] as String,
        essentialsActualTotal: json['essentials_actual_total'] as String,
        discretionaryActualTotal: json['discretionary_actual_total'] as String,
        projectedNet: json['projected_net'] as String?,
        actualNetSoFar: json['actual_net_so_far'] as String,
      );
}

class BudgetSuggestion {
  BudgetSuggestion({required this.categoryId, required this.isEssential, required this.suggestedAmount});

  final String categoryId;
  final bool isEssential;
  final String suggestedAmount;

  factory BudgetSuggestion.fromJson(Map<String, dynamic> json) => BudgetSuggestion(
        categoryId: json['category_id'] as String,
        isEssential: json['is_essential'] as bool,
        suggestedAmount: json['suggested_amount'] as String,
      );
}
```

- [ ] **Step 4: Create the budget providers**

Create `frontend/money_tracker_app/lib/features/budget/providers/budget_provider.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';

import '../../../core/api_client.dart';
import '../models/budget_state.dart';

// autoDispose for the same reason as monthlySummaryProvider (see
// dashboard_provider.dart): HomeShell tears this screen down on every tab
// switch, so a plain FutureProvider would go stale after the first load.
final budgetProvider = FutureProvider.autoDispose<BudgetState>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/budget');
  return BudgetState.fromJson(response.data as Map<String, dynamic>);
});

final budgetSuggestionsProvider = FutureProvider.autoDispose<List<BudgetSuggestion>>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/budget/suggestions');
  final data = response.data as List<dynamic>;
  return data.map((json) => BudgetSuggestion.fromJson(json as Map<String, dynamic>)).toList();
});

final budgetControllerProvider =
    StateNotifierProvider<BudgetController, AsyncValue<void>>((ref) {
  return BudgetController(ref.watch(apiClientProvider), ref);
});

class BudgetController extends StateNotifier<AsyncValue<void>> {
  BudgetController(this._apiClient, this._ref) : super(const AsyncData(null));

  final ApiClient _apiClient;
  final Ref _ref;

  Future<void> setIncomeTarget(String amount) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.put('/budget/income-target', data: {'amount': amount});
      _ref.invalidate(budgetProvider);
    });
  }

  Future<void> setLine({required String categoryId, required bool isEssential, required String amount}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.put('/budget/lines', data: {
        'category_id': categoryId,
        'is_essential': isEssential,
        'amount': amount,
      });
      _ref.invalidate(budgetProvider);
    });
  }

  Future<void> acceptSuggestion({required String categoryId, required bool isEssential}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.post('/budget/lines/accept-suggestion', data: {
        'category_id': categoryId,
        'is_essential': isEssential,
      });
      _ref.invalidate(budgetProvider);
      _ref.invalidate(budgetSuggestionsProvider);
    });
  }
}
```

- [ ] **Step 5: Create the budget screen**

Create `frontend/money_tracker_app/lib/features/budget/screens/budget_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/budget_state.dart';
import '../providers/budget_provider.dart';

class BudgetScreen extends ConsumerStatefulWidget {
  const BudgetScreen({super.key});

  @override
  ConsumerState<BudgetScreen> createState() => _BudgetScreenState();
}

class _BudgetScreenState extends ConsumerState<BudgetScreen> {
  final _incomeTargetController = TextEditingController();
  bool _incomeTargetSeeded = false;
  final Map<String, TextEditingController> _lineControllers = {};

  TextEditingController _controllerFor(String categoryId, bool isEssential) {
    final key = '$categoryId-$isEssential';
    return _lineControllers.putIfAbsent(key, () => TextEditingController());
  }

  @override
  void dispose() {
    _incomeTargetController.dispose();
    for (final controller in _lineControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final budgetAsync = ref.watch(budgetProvider);
    final controllerState = ref.watch(budgetControllerProvider);

    ref.listen(budgetControllerProvider, (previous, next) {
      if (next.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update budget: ${next.error}')),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Budget')),
      body: budgetAsync.when(
        data: (state) {
          if (!_incomeTargetSeeded && state.incomeTarget != null) {
            _incomeTargetController.text = state.incomeTarget!;
            _incomeTargetSeeded = true;
          }
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('income_target_field'),
                      controller: _incomeTargetController,
                      decoration: const InputDecoration(labelText: 'Income target'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    ),
                  ),
                  IconButton(
                    key: const Key('save_income_target_button'),
                    icon: const Icon(Icons.check),
                    onPressed: controllerState.isLoading
                        ? null
                        : () => ref
                            .read(budgetControllerProvider.notifier)
                            .setIncomeTarget(_incomeTargetController.text),
                  ),
                ],
              ),
              Text('Actual income: ${state.actualIncomeThisMonth}', key: const Key('actual_income')),
              const SizedBox(height: 12),
              Text(
                state.projectedNet != null
                    ? 'Projected net: ${state.projectedNet}'
                    : 'Projected net: set an income target',
                key: const Key('projected_net'),
              ),
              Text('Actual net so far: ${state.actualNetSoFar}', key: const Key('actual_net_so_far')),
              const SizedBox(height: 24),
              _BudgetSection(
                title: 'Essentials',
                budgetTotal: state.essentialsBudgetTotal,
                actualTotal: state.essentialsActualTotal,
                lines: state.lines.where((line) => line.isEssential).toList(),
                controllerFor: _controllerFor,
              ),
              const SizedBox(height: 24),
              _BudgetSection(
                title: 'Discretionary',
                budgetTotal: state.discretionaryBudgetTotal,
                actualTotal: state.discretionaryActualTotal,
                lines: state.lines.where((line) => !line.isEssential).toList(),
                controllerFor: _controllerFor,
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load budget: $error')),
      ),
    );
  }
}

class _BudgetSection extends StatelessWidget {
  const _BudgetSection({
    required this.title,
    required this.budgetTotal,
    required this.actualTotal,
    required this.lines,
    required this.controllerFor,
  });

  final String title;
  final String budgetTotal;
  final String actualTotal;
  final List<BudgetLine> lines;
  final TextEditingController Function(String categoryId, bool isEssential) controllerFor;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        Text('Budget: $budgetTotal — Actual: $actualTotal'),
        ...lines.map(
          (line) => _BudgetLineTile(line: line, controller: controllerFor(line.categoryId, line.isEssential)),
        ),
      ],
    );
  }
}

BudgetSuggestion? _matchingSuggestion(List<BudgetSuggestion> suggestions, String categoryId, bool isEssential) {
  for (final suggestion in suggestions) {
    if (suggestion.categoryId == categoryId && suggestion.isEssential == isEssential) {
      return suggestion;
    }
  }
  return null;
}

class _BudgetLineTile extends ConsumerWidget {
  const _BudgetLineTile({required this.line, required this.controller});

  final BudgetLine line;
  final TextEditingController controller;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final keySuffix = '${line.categoryId}-${line.isEssential}';
    final hasBudget = line.budgetAmount != null;
    final fraction = hasBudget
        ? ((double.tryParse(line.actualThisMonth) ?? 0) / (double.tryParse(line.budgetAmount!) ?? 1))
            .clamp(0.0, 1.0)
        : 0.0;
    final suggestionsAsync = ref.watch(budgetSuggestionsProvider);
    final suggestion = line.eligibleForSuggestion
        ? suggestionsAsync.maybeWhen(
            data: (suggestions) => _matchingSuggestion(suggestions, line.categoryId, line.isEssential),
            orElse: () => null,
          )
        : null;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${line.categoryName} (${line.isEssential ? 'Essential' : 'Discretionary'})'),
          if (hasBudget) ...[
            Text('${line.actualThisMonth} / ${line.budgetAmount}', key: Key('line_progress_$keySuffix')),
            FractionallySizedBox(
              widthFactor: fraction,
              alignment: Alignment.centerLeft,
              child: Container(height: 8, color: Theme.of(context).colorScheme.primary),
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: Key('line_amount_field_$keySuffix'),
                    controller: controller,
                    decoration: const InputDecoration(labelText: 'Set budget'),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  ),
                ),
                IconButton(
                  key: Key('save_line_button_$keySuffix'),
                  icon: const Icon(Icons.check),
                  onPressed: () => ref.read(budgetControllerProvider.notifier).setLine(
                        categoryId: line.categoryId,
                        isEssential: line.isEssential,
                        amount: controller.text,
                      ),
                ),
                if (suggestion != null)
                  TextButton(
                    key: Key('accept_suggestion_button_$keySuffix'),
                    onPressed: () => ref.read(budgetControllerProvider.notifier).acceptSuggestion(
                          categoryId: line.categoryId,
                          isEssential: line.isEssential,
                        ),
                    child: Text('Use suggestion: ${suggestion.suggestedAmount}'),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
```

- [ ] **Step 6: Wire the Budget tab into `HomeShell`**

Edit `frontend/money_tracker_app/lib/core/home_shell.dart`:

```dart
import 'package:flutter/material.dart';

import '../features/budget/screens/budget_screen.dart';
import '../features/categories/screens/category_list_screen.dart';
import '../features/dashboard/screens/dashboard_screen.dart';
import '../features/transactions/screens/transaction_entry_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _screens = [
    DashboardScreen(),
    TransactionEntryScreen(),
    CategoryListScreen(),
    BudgetScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_index],
      bottomNavigationBar: NavigationBar(
        key: const Key('home_bottom_nav'),
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.add_circle), label: 'Add'),
          NavigationDestination(icon: Icon(Icons.category), label: 'Categories'),
          NavigationDestination(icon: Icon(Icons.savings), label: 'Budget'),
        ],
      ),
    );
  }
}
```

- [ ] **Step 7: Add a Budget-tab test to `home_shell_test.dart`**

Edit `frontend/money_tracker_app/test/core/home_shell_test.dart`, adding the budget imports and a new test:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/core/home_shell.dart';
import 'package:money_tracker_app/features/budget/models/budget_state.dart';
import 'package:money_tracker_app/features/budget/providers/budget_provider.dart';
import 'package:money_tracker_app/features/budget/screens/budget_screen.dart';
import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/dashboard/models/monthly_summary.dart';
import 'package:money_tracker_app/features/dashboard/providers/dashboard_provider.dart';

void main() {
  testWidgets(
      'Revisiting the Dashboard tab refetches the summary, proving HomeShell '
      'tears the screen down on tab switch rather than preserving it '
      '(monthlySummaryProvider relies on this to stay fresh — see the '
      'comment on that provider)', (tester) async {
    var fetchCount = 0;
    final summary = MonthlySummary(
      month: '2026-09',
      totalIncome: '1000.00',
      totalExpense: '400.00',
      net: '600.00',
      byCategory: const [],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          monthlySummaryProvider.overrideWith((ref) async {
            fetchCount++;
            return summary;
          }),
          categoryListProvider.overrideWith((ref) async => <Category>[]),
        ],
        child: const MaterialApp(home: HomeShell()),
      ),
    );
    await tester.pump();

    // Initial load of the Dashboard tab fetches once.
    expect(fetchCount, 1);

    // Switch to the Categories tab, then back to Dashboard.
    await tester.tap(find.text('Categories'));
    await tester.pump();
    await tester.tap(find.text('Dashboard'));
    await tester.pump();

    // autoDispose + HomeShell's full teardown on tab switch means revisiting
    // Dashboard triggers a fresh fetch. If HomeShell ever switches to an
    // IndexedStack (preserving tab state), this count would stay at 1 and
    // this test would catch the regression.
    expect(fetchCount, 2);
  });

  testWidgets('Budget tab is present and shows BudgetScreen when selected', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          monthlySummaryProvider.overrideWith((ref) async => MonthlySummary(
                month: '2026-09',
                totalIncome: '0.00',
                totalExpense: '0.00',
                net: '0.00',
                byCategory: const [],
              )),
          categoryListProvider.overrideWith((ref) async => <Category>[]),
          budgetProvider.overrideWith((ref) async => BudgetState(
                incomeTarget: null,
                actualIncomeThisMonth: '0.00',
                lines: const [],
                essentialsBudgetTotal: '0.00',
                discretionaryBudgetTotal: '0.00',
                essentialsActualTotal: '0.00',
                discretionaryActualTotal: '0.00',
                projectedNet: null,
                actualNetSoFar: '0.00',
              )),
          budgetSuggestionsProvider.overrideWith((ref) async => <BudgetSuggestion>[]),
        ],
        child: const MaterialApp(home: HomeShell()),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Budget'));
    await tester.pump();

    expect(find.byType(BudgetScreen), findsOneWidget);
  });
}
```

- [ ] **Step 8: Run the frontend tests and see them pass**

Run: `cd frontend/money_tracker_app && flutter test`
Expected: PASS, all tests green.

- [ ] **Step 9: Run `flutter analyze`**

Run: `cd frontend/money_tracker_app && flutter analyze`
Expected: No issues found.

- [ ] **Step 10: Commit**

```bash
git add frontend/money_tracker_app/lib/features/budget frontend/money_tracker_app/lib/core/home_shell.dart \
  frontend/money_tracker_app/test/features/budget frontend/money_tracker_app/test/core/home_shell_test.dart
git commit -m "feat: add Budget tab with income target, projected net, and per-category budget lines"
```

**Manual click-through checkpoint (full feature, end to end):** log in to the real app. Set an income target. Add expense transactions tagged both Essential and Discretionary for the same category across 3 different months (or use existing history if you have it) and confirm the Budget tab shows a "Use suggestion" option once eligible, with a sane computed number. Set a manual budget on a cold-start line. Confirm the Essentials/Discretionary totals, projected net, and actual-vs-budget figures all match what you'd compute by hand. Confirm the Budget tab survives switching away and back (data refetches, doesn't error). This is the final feature of M3 — verify it end to end before moving to the final review.

---

## Final Review

Once all 7 tasks are complete and committed:

1. Run the full backend suite: `cd backend && python -m pytest -q` — expect all green.
2. Run `flutter analyze` and `flutter test` from `frontend/money_tracker_app/` — expect clean and all green.
3. Do the full manual click-through described in Task 7's checkpoint if it hasn't been done yet on the actual deployed Render backend + Supabase project (not just local).
4. Use `superpowers:requesting-code-review`'s `code-reviewer.md` template for a whole-branch review on the most capable available model, per the `subagent-driven-development` process this plan is meant to run under.
5. Use `superpowers:finishing-a-development-branch` to merge/PR the `feature/m3-budget-engine` branch back to `main`, following the same branch-discipline pattern used for M1 and M2 (push and wait for explicit go-ahead before opening a PR, unless told otherwise).

