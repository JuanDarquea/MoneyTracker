# M2 — Categories & Monthly View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship M2 from `Planning/02_agent_structure.md`'s milestone table — per-user category CRUD and a monthly summary endpoint on the backend, category management screens and a monthly dashboard on the frontend — on top of the M1 skateboard, which is live on Render + Supabase.

**Architecture:** Same stack as M1 (FastAPI/SQLAlchemy/Alembic backend, Flutter/Riverpod frontend). Categories move from a global, M1-seeded table to a real per-user resource (archive-only removal); a new read-only summary endpoint aggregates a user's transactions for one calendar month. The frontend gains a 3-tab navigation shell (Dashboard / Add / Categories) to host the two new screens, and its M1 placeholder category list is replaced with a real fetch.

**Tech Stack:** Same as M1 — Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest + httpx, Flutter 3.47, Riverpod, `dio`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-16-m2-categories-and-monthly-view-design.md`

## Global Constraints

- All money fields use `Decimal` end to end — never `float` (unchanged from M1).
- Categories are per-user (`user_id` column), never global, never hard-deleted — only archived (`is_archived`).
- No `DELETE /api/v1/categories/{id}` route — archiving is the only removal path, exposed via `PATCH`.
- `is_essential` is only ever set on an expense category; rejected (422) on income.
- The monthly summary endpoint (`GET /api/v1/summary`) covers exactly one calendar month per call, defaulting to the current month — no month-over-month or 3-month-average comparison (that's M3's budget-engine territory).
- Backend tests always run against local Docker Postgres (`TEST_DATABASE_URL`), never a live Supabase project.
- Frontend widget tests never make real network calls — fake data via Riverpod provider overrides.
- **Manual click-through, not just automated tests:** after each frontend feature lands (category screens, transaction entry using real categories, dashboard), click through it live in the browser against the real local backend before moving to the next task. After the whole milestone, click through once more against the real Supabase project data end to end. Automated tests catch logic bugs; only clicking through catches integration bugs like M1's Render `SUPABASE_URL` miss.
- No hard delete of categories, no un-archiving, no charting library, no transaction history/list screen — all explicitly out of scope per the spec.

---

## File Structure

```
backend/
├── alembic/versions/0002_categories_per_user.py   # [CREATE]
├── app/
│   ├── models/category.py                          # [MODIFY] user_id, is_archived
│   ├── schemas/category.py                          # [CREATE]
│   ├── schemas/summary.py                            # [CREATE]
│   ├── schemas/__init__.py                           # [MODIFY]
│   ├── services/categories.py                        # [CREATE]
│   ├── services/summary.py                           # [CREATE]
│   ├── services/transactions.py                      # [unchanged — ownership check lives in the route]
│   ├── api/v1/categories.py                          # [CREATE]
│   ├── api/v1/summary.py                             # [CREATE]
│   ├── api/v1/transactions.py                        # [MODIFY] category ownership check
│   └── api/v1/router.py                              # [MODIFY] register new routers
└── tests/
    ├── conftest.py                                   # [MODIFY] per-user seeded_category, new fixtures
    ├── test_categories_api.py                        # [CREATE]
    ├── test_summary_api.py                            # [CREATE]
    └── test_transactions_api.py                       # [MODIFY] ownership test + fix isolation test

frontend/money_tracker_app/
├── lib/
│   ├── core/home_shell.dart                           # [CREATE]
│   ├── features/auth/screens/login_screen.dart        # [MODIFY] redirect to HomeShell
│   ├── features/categories/
│   │   ├── models/category.dart                       # [CREATE]
│   │   ├── providers/category_provider.dart           # [CREATE]
│   │   └── screens/{category_list_screen.dart, category_form_screen.dart}  # [CREATE]
│   ├── features/dashboard/
│   │   ├── models/monthly_summary.dart                # [CREATE]
│   │   ├── providers/dashboard_provider.dart          # [CREATE]
│   │   └── screens/dashboard_screen.dart              # [CREATE]
│   └── features/transactions/screens/transaction_entry_screen.dart  # [MODIFY] real categories
└── test/features/
    ├── categories/{category_list_screen_test.dart, category_form_screen_test.dart}  # [CREATE]
    ├── dashboard/dashboard_screen_test.dart            # [CREATE]
    └── transactions/transaction_entry_screen_test.dart # [MODIFY]
```

---

## Task 1: Categories become per-user (model + migration)

**Files:**
- Modify: `backend/app/models/category.py`
- Create: `backend/alembic/versions/0002_categories_per_user.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `app.db.base.Base` (M1).
- Produces: `Category.user_id: uuid.UUID`, `Category.is_archived: bool` — every later task's model/service/schema code assumes these two fields exist.

- [ ] **Step 1: Update the `Category` model**

`backend/app/models/category.py` (full file):
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
    is_essential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Write the migration**

`backend/alembic/versions/0002_categories_per_user.py`:
```python
"""categories become per-user, gain an archive flag

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The 7 categories M1 seeded had no owner (categories were global), and
    # are referenced by the 2 transactions created while manually verifying
    # M1/the Render deploy. All of that is pre-launch smoke-test data, not
    # real user data. Both tables are cleared here so the new NOT NULL
    # user_id column can be added cleanly, without a backfill default.
    # Nothing re-seeds this table going forward -- app.services.categories.
    # ensure_default_categories creates a user's 7 starter categories
    # lazily, the first time it needs their category list and finds none.
    op.execute("DELETE FROM transactions")
    op.execute("DELETE FROM categories")

    op.add_column("categories", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False))
    op.add_column(
        "categories",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_categories_user_id", table_name="categories")
    op.drop_column("categories", "is_archived")
    op.drop_column("categories", "user_id")
```

- [ ] **Step 3: Update the `seeded_category` fixture to own its category**

In `backend/tests/conftest.py`, the `seeded_category` fixture currently creates a `Category` with no `user_id`, which no longer compiles against the model. Replace it:

```python
@pytest.fixture()
def seeded_category(db: Session, user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Food",
        type=CategoryType.EXPENSE,
        is_essential=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
```

(Only the `user_id=user_id` line and the fixture's dependency on the existing `user_id` fixture are new — everything else matches the current fixture.)

- [ ] **Step 4: Run the full backend suite to confirm it still collects/fails only where expected**

```bash
cd backend && source .venv/bin/activate
python -m pytest -v
```
Expected: existing tests that use `seeded_category` still PASS (fixture now supplies `user_id`); no import/collection errors.

- [ ] **Step 5: Apply the migration to local Docker Postgres and verify it's reversible**

```bash
docker compose -f ../docker-compose.dev.yml up -d
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```
Expected: all three commands succeed with no errors. Manual check — confirm the column exists:
```bash
docker exec -it moneytracker-postgres-1 psql -U moneytracker -d moneytracker -c "\d categories"
```
Expected output includes `user_id` (`uuid`, not null) and `is_archived` (`boolean`, not null, default `false`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/category.py backend/alembic/versions/0002_categories_per_user.py backend/tests/conftest.py
git commit -m "feat: make categories per-user with an archive flag"
```

---

## Task 2: Category Pydantic schemas

**Files:**
- Create: `backend/app/schemas/category.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_category_schemas.py`

**Interfaces:**
- Consumes: `app.models.CategoryType` (M1).
- Produces: `app.schemas.category.CategoryCreate` (`name: str`, `type: CategoryType`, `is_essential: bool | None = None`), `CategoryUpdate` (`name`, `is_essential`, `is_archived`, all optional), `CategoryRead` (adds `id`, `is_archived`). `CategoryCreate`/`CategoryUpdate` reject a blank or >64-char `name`; `CategoryCreate` rejects `is_essential` set alongside `type=income`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_category_schemas.py`:
```python
import uuid

import pytest
from pydantic import ValidationError

from app.models import CategoryType
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate


def test_create_expense_category_with_essential_flag():
    payload = CategoryCreate(name="Gym", type=CategoryType.EXPENSE, is_essential=False)
    assert payload.name == "Gym"
    assert payload.is_essential is False


def test_create_income_category_rejects_is_essential():
    with pytest.raises(ValidationError):
        CategoryCreate(name="Freelance", type=CategoryType.INCOME, is_essential=True)


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
        is_essential = True
        is_archived = False

    read = CategoryRead.model_validate(FakeOrmCategory())
    assert read.name == "Food"
    assert read.is_archived is False
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_category_schemas.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.schemas.category'`

- [ ] **Step 3: Implement**

`backend/app/schemas/category.py`:
```python
import uuid

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models import CategoryType


def _validate_name(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 64:
        raise ValueError("name must be between 1 and 64 characters")
    return value


class CategoryBase(BaseModel):
    name: str
    type: CategoryType
    is_essential: bool | None = None

    @field_validator("name")
    @classmethod
    def name_is_valid(cls, value: str) -> str:
        return _validate_name(value)

    @model_validator(mode="after")
    def is_essential_only_for_expense(self) -> "CategoryBase":
        if self.type == CategoryType.INCOME and self.is_essential is not None:
            raise ValueError("is_essential can only be set on an expense category")
        return self


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    is_essential: bool | None = None
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
    is_essential: bool | None
    is_archived: bool
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_category_schemas.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Export from the schemas package**

`backend/app/schemas/__init__.py` (full file):
```python
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate

__all__ = [
    "CategoryCreate",
    "CategoryRead",
    "CategoryUpdate",
    "TransactionCreate",
    "TransactionRead",
    "TransactionUpdate",
]
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/category.py backend/app/schemas/__init__.py backend/tests/test_category_schemas.py
git commit -m "feat: add category schemas with essential-only-for-expense validation"
```

---

## Task 3: Category service layer + API endpoints

**Files:**
- Create: `backend/app/services/categories.py`
- Create: `backend/app/api/v1/categories.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_categories_api.py`

**Interfaces:**
- Consumes: `get_db` (M1), `get_current_user_id` (M1), `CategoryCreate`/`CategoryUpdate`/`CategoryRead` (Task 2).
- Produces: `app.services.categories.{ensure_default_categories, list_categories, get_category, create_category, update_category}` (all take `db: Session, user_id: uuid.UUID, ...`). Routes: `GET /api/v1/categories` (lazy-seeds defaults, `?include_archived=` query param), `POST /api/v1/categories`, `PATCH /api/v1/categories/{id}` — all scoped to the caller, all requiring a valid bearer token.

- [ ] **Step 1: Write the failing API tests**

`backend/tests/test_categories_api.py`:
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
        json={"name": "Gym", "type": "expense", "is_essential": False},
        headers=auth_headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Gym"
    assert created["is_archived"] is False


def test_create_category_rejects_is_essential_on_income(client, auth_headers):
    response = client.post(
        "/api/v1/categories",
        json={"name": "Freelance", "type": "income", "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_category_name_and_essential(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense", "is_essential": False},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"name": "Gym Membership", "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Gym Membership"
    assert response.json()["is_essential"] is True


def test_update_category_rejects_is_essential_on_income(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Freelance", "type": "income"},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


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

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_categories_api.py -v
```
Expected: `ModuleNotFoundError` / 404s — the service and routes don't exist yet.

- [ ] **Step 3: Implement the service layer**

`backend/app/services/categories.py`:
```python
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, CategoryType
from app.schemas.category import CategoryCreate, CategoryUpdate

DEFAULT_CATEGORIES: list[tuple[str, CategoryType, bool | None]] = [
    ("Salary", CategoryType.INCOME, None),
    ("Food", CategoryType.EXPENSE, True),
    ("Transport", CategoryType.EXPENSE, True),
    ("Housing", CategoryType.EXPENSE, True),
    ("Utilities", CategoryType.EXPENSE, True),
    ("Entertainment", CategoryType.EXPENSE, False),
    ("Shopping", CategoryType.EXPENSE, False),
]


def ensure_default_categories(db: Session, user_id: uuid.UUID) -> None:
    """Create this user's 7 starter categories if they have none yet.

    Idempotent: a user who already has any category (even just a custom
    one) is left untouched -- this only fires for a brand new user.
    """
    stmt = select(Category.id).where(Category.user_id == user_id).limit(1)
    if db.scalars(stmt).first() is not None:
        return

    for name, cat_type, is_essential in DEFAULT_CATEGORIES:
        db.add(
            Category(
                id=uuid.uuid4(),
                user_id=user_id,
                name=name,
                type=cat_type,
                is_essential=is_essential,
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

- [ ] **Step 4: Implement the routes**

`backend/app/api/v1/categories.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import CategoryType
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
    if payload.is_essential is not None and category.type == CategoryType.INCOME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="is_essential can only be set on an expense category",
        )
    return categories_service.update_category(db, category, payload)
```

Update `backend/app/api/v1/router.py`:
```python
from fastapi import APIRouter

from app.api.v1 import categories, health, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_categories_api.py -v
```
Expected: all 8 tests PASS. Then run the full suite: `pytest -v` — everything from Tasks 1-2 should still pass too.

- [ ] **Step 6: Manual verification against the running local backend**

```bash
uvicorn app.main:app --reload &
sleep 1

TOKEN=$(python -c "
import jwt, uuid
from datetime import datetime, timedelta, timezone
print(jwt.encode({'sub': str(uuid.uuid4()), 'aud': 'authenticated', 'exp': datetime.now(timezone.utc)+timedelta(hours=1)}, 'dev-only-change-me', algorithm='HS256'))
")

curl -s http://localhost:8000/api/v1/categories -H "Authorization: Bearer $TOKEN" | python -m json.tool
kill %1
```
Expected: JSON array of 7 categories (Salary, Food, Transport, Housing, Utilities, Entertainment, Shopping) — proves the lazy-seed path actually runs against a real server process, not just the test client.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/categories.py backend/app/api/v1/categories.py backend/app/api/v1/router.py backend/tests/test_categories_api.py
git commit -m "feat: add per-user category CRUD with lazy-seeded defaults"
```

---

## Task 4: Fix transaction category-ownership validation

**Files:**
- Modify: `backend/app/api/v1/transactions.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_transactions_api.py`

**Interfaces:**
- Consumes: `app.services.categories.get_category` (Task 3).
- Produces: `POST /api/v1/transactions` and `PATCH /api/v1/transactions/{id}` now 404 if `category_id` doesn't belong to the caller.

Under M1's global categories, `create_transaction`/`update_transaction` never checked that `category_id` belonged to anyone in particular — harmless when every category belonged to everyone. Now that categories are per-user (Task 1), that's a real bug: user A could create a transaction against user B's category. This task closes it, and fixes the one existing test that (correctly, under the old rules) relied on that gap.

- [ ] **Step 1: Add fixtures for a second user's category**

In `backend/tests/conftest.py`, add (the existing `seeded_category` fixture is untouched):
```python
@pytest.fixture()
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def other_user_category(db: Session, other_user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        user_id=other_user_id,
        name="Rent",
        type=CategoryType.EXPENSE,
        is_essential=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
```

- [ ] **Step 2: Write the failing regression test, and fix the now-outdated isolation test**

In `backend/tests/test_transactions_api.py`, add:
```python
def test_create_transaction_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(other_user_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
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
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(other_user_category.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404
```

`test_transactions_are_isolated_between_users` currently has user B create a transaction against `seeded_category` (owned by user A) — that will start failing with 404 once ownership is enforced, which is correct behavior but breaks the test's own setup. Replace its body:

```python
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
        },
        headers=user_b_headers,
    ).json()

    # User A's list contains only their own transaction, never user B's.
    user_a_list = client.get("/api/v1/transactions", headers=auth_headers)
    assert user_a_list.status_code == 200
    user_a_ids = {item["id"] for item in user_a_list.json()}
    assert user_a_ids == {user_a_transaction["id"]}
    assert user_b_transaction["id"] not in user_a_ids

    # User A cannot fetch, patch, or delete user B's transaction by id (404, not 403 —
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
```

(Only the signature gained `other_user_id, other_user_category`, `user_b_headers` now uses `other_user_id` instead of a throwaway `uuid.uuid4()`, and `user_b_transaction`'s `category_id` now uses `other_user_category.id` instead of the shared `seeded_category.id`.)

- [ ] **Step 3: Run to verify the new tests fail and the isolation test would fail without the fix**

```bash
pytest tests/test_transactions_api.py -v
```
Expected: `test_create_transaction_rejects_other_users_category` and `test_update_transaction_rejects_other_users_category` FAIL (currently return 201/200, not 404).

- [ ] **Step 4: Implement the ownership check**

In `backend/app/api/v1/transactions.py`, add the import and two checks:
```python
from app.services import categories as categories_service
```
(add alongside the existing `from app.services import transactions as transactions_service`)

```python
@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    if categories_service.get_category(db, user_id, payload.category_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return transactions_service.create_transaction(db, user_id, payload)
```

```python
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
    if payload.category_id is not None and categories_service.get_category(db, user_id, payload.category_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return transactions_service.update_transaction(db, txn, payload)
```

(`create_transaction`/`update_transaction` route function names shadow the service functions of the same name — this already matched the existing M1 file's style, unchanged here.)

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_transactions_api.py -v
```
Expected: all tests in the file PASS, including the 2 new ones and the rewritten isolation test. Then `pytest -v` for the full suite.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/transactions.py backend/tests/conftest.py backend/tests/test_transactions_api.py
git commit -m "fix: reject transactions created against another user's category"
```

---

## Task 5: Monthly summary endpoint

**Files:**
- Create: `backend/app/schemas/summary.py`
- Create: `backend/app/services/summary.py`
- Create: `backend/app/api/v1/summary.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_summary_api.py`
- Modify: `backend/tests/conftest.py` (one more fixture)

**Interfaces:**
- Consumes: `get_db`, `get_current_user_id` (M1); `Category`, `Transaction`, `TransactionType` (M1/Task 1).
- Produces: `GET /api/v1/summary?month=YYYY-MM` (defaults to the current month) → `app.schemas.summary.MonthlySummary` (`month: str`, `total_income: Decimal`, `total_expense: Decimal`, `net: Decimal`, `by_category: list[CategoryBreakdownItem]`), where `CategoryBreakdownItem` has `category_id: uuid.UUID`, `category_name: str`, `type: CategoryType`, `amount: Decimal`.

- [ ] **Step 1: Add a second seeded category (income) for aggregation tests**

In `backend/tests/conftest.py`, add:
```python
@pytest.fixture()
def seeded_income_category(db: Session, user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Salary",
        type=CategoryType.INCOME,
        is_essential=None,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_summary_api.py`:
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
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "20.00", "occurred_on": "2026-09-05"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "15.50", "occurred_on": "2026-09-10"},
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
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "999.00", "occurred_on": "2026-08-15"},
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
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "10.00", "occurred_on": today},
        headers=auth_headers,
    )

    response = client.get("/api/v1/summary", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total_expense"] == "10.00"


def test_summary_is_isolated_between_users(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "50.00", "occurred_on": "2026-09-05"},
        headers=auth_headers,
    )

    other_headers = _auth_headers_for(uuid.uuid4())
    response = client.get("/api/v1/summary?month=2026-09", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["total_expense"] == "0.00"
```

- [ ] **Step 3: Run to verify failure**

```bash
pytest tests/test_summary_api.py -v
```
Expected: 404s — the route doesn't exist yet.

- [ ] **Step 4: Implement the schema**

`backend/app/schemas/summary.py`:
```python
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
```

- [ ] **Step 5: Implement the service**

`backend/app/services/summary.py`:
```python
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
```

- [ ] **Step 6: Implement the route**

`backend/app/api/v1/summary.py`:
```python
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
```

Update `backend/app/api/v1/router.py` (full file):
```python
from fastapi import APIRouter

from app.api.v1 import categories, health, summary, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(summary.router)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_summary_api.py -v
```
Expected: all 4 tests PASS. Then run the full suite: `pytest -v`.

- [ ] **Step 8: Manual verification against the running local backend**

```bash
uvicorn app.main:app --reload &
sleep 1
open http://localhost:8000/docs || xdg-open http://localhost:8000/docs
```
In the Swagger UI, use "Authorize" is not wired for bearer tokens here, so instead run a direct curl with a freshly minted token (same pattern as Task 3 Step 6) against `/api/v1/summary` and confirm the response shape matches `MonthlySummary` with zeroed totals for a brand-new test user. Then `kill %1`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/summary.py backend/app/services/summary.py backend/app/api/v1/summary.py backend/app/api/v1/router.py backend/tests/test_summary_api.py backend/tests/conftest.py
git commit -m "feat: add monthly summary endpoint"
```

---

## Task 6: Frontend category model, provider, and screens

**Files:**
- Create: `frontend/money_tracker_app/lib/features/categories/models/category.dart`
- Create: `frontend/money_tracker_app/lib/features/categories/providers/category_provider.dart`
- Create: `frontend/money_tracker_app/lib/features/categories/screens/category_list_screen.dart`
- Create: `frontend/money_tracker_app/lib/features/categories/screens/category_form_screen.dart`
- Test: `frontend/money_tracker_app/test/features/categories/category_list_screen_test.dart`
- Test: `frontend/money_tracker_app/test/features/categories/category_form_screen_test.dart`

**Interfaces:**
- Consumes: `apiClientProvider` (M1, `lib/core/api_client.dart`).
- Produces: `Category` (`id, name, type, isEssential, isArchived`), `categoryListProvider` (`FutureProvider<List<Category>>`, GETs `/categories`), `categoryControllerProvider` (`StateNotifierProvider<CategoryController, AsyncValue<void>>` with `create({name, type, isEssential})`, `archive(categoryId)`, `setEssential(categoryId, isEssential)` — each invalidates `categoryListProvider` on success). `CategoryListScreen`, `CategoryFormScreen` widgets.

- [ ] **Step 1: Category model**

`frontend/money_tracker_app/lib/features/categories/models/category.dart`:
```dart
class Category {
  Category({
    required this.id,
    required this.name,
    required this.type,
    required this.isEssential,
    required this.isArchived,
  });

  final String id;
  final String name;
  final String type;
  final bool? isEssential;
  final bool isArchived;

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as String,
        name: json['name'] as String,
        type: json['type'] as String,
        isEssential: json['is_essential'] as bool?,
        isArchived: json['is_archived'] as bool,
      );
}
```

- [ ] **Step 2: Category providers**

`frontend/money_tracker_app/lib/features/categories/providers/category_provider.dart`:
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

  Future<void> create({required String name, required String type, bool? isEssential}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.post('/categories', data: {
        'name': name,
        'type': type,
        if (isEssential != null) 'is_essential': isEssential,
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

  Future<void> setEssential(String categoryId, bool isEssential) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _apiClient.dio.patch('/categories/$categoryId', data: {'is_essential': isEssential});
      _ref.invalidate(categoryListProvider);
    });
  }
}
```

- [ ] **Step 3: Category list screen**

`frontend/money_tracker_app/lib/features/categories/screens/category_list_screen.dart`:
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
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (category.type == 'expense')
            Switch(
              key: Key('essential_toggle_${category.id}'),
              value: category.isEssential ?? false,
              onChanged: (value) =>
                  ref.read(categoryControllerProvider.notifier).setEssential(category.id, value),
            ),
          IconButton(
            key: Key('archive_button_${category.id}'),
            icon: const Icon(Icons.archive_outlined),
            onPressed: () => ref.read(categoryControllerProvider.notifier).archive(category.id),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4: Category form screen**

`frontend/money_tracker_app/lib/features/categories/screens/category_form_screen.dart`:
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
  bool _isEssential = false;

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
                if (_type == 'income') _isEssential = false;
              }),
            ),
            if (_type == 'expense')
              SwitchListTile(
                key: const Key('category_essential_toggle'),
                title: const Text('Essential'),
                value: _isEssential,
                onChanged: (value) => setState(() => _isEssential = value),
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
          isEssential: _type == 'expense' ? _isEssential : null,
        );
  }
}
```

- [ ] **Step 5: Write the widget tests**

`frontend/money_tracker_app/test/features/categories/category_list_screen_test.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/features/categories/models/category.dart';
import 'package:money_tracker_app/features/categories/providers/category_provider.dart';
import 'package:money_tracker_app/features/categories/screens/category_list_screen.dart';

void main() {
  testWidgets(
      'CategoryListScreen renders fetched categories with an essential toggle only for expense categories',
      (tester) async {
    final categories = [
      Category(id: '1', name: 'Food', type: 'expense', isEssential: true, isArchived: false),
      Category(id: '2', name: 'Salary', type: 'income', isEssential: null, isArchived: false),
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
    expect(find.byKey(const Key('essential_toggle_1')), findsOneWidget);
    expect(find.byKey(const Key('essential_toggle_2')), findsNothing);
    expect(find.byKey(const Key('add_category_button')), findsOneWidget);
  });
}
```

`frontend/money_tracker_app/test/features/categories/category_form_screen_test.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:money_tracker_app/features/categories/screens/category_form_screen.dart';

void main() {
  // CategoryFormScreen watches categoryControllerProvider directly during
  // build (for its loading/error state), which depends on apiClientProvider
  // -> supabaseClientProvider -> Supabase.instance.client, same as M1's
  // TransactionEntryScreen. This test never submits, so no real network
  // call happens, but Supabase.initialize() still needs to have run once
  // (see test/widget_test.dart for why the shared_preferences channel is
  // mocked here too).
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

  testWidgets('CategoryFormScreen essential toggle only shows for expense type', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: CategoryFormScreen())),
    );

    expect(find.byKey(const Key('category_essential_toggle')), findsOneWidget);

    await tester.tap(find.text('Income'));
    await tester.pump();

    expect(find.byKey(const Key('category_essential_toggle')), findsNothing);
  });
}
```

- [ ] **Step 6: Run the frontend tests**

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
cd frontend/money_tracker_app
flutter test test/features/categories/
```
Expected: both new test files PASS.

- [ ] **Step 7: Manual click-through against the real local backend**

With `uvicorn app.main:app --reload` running locally (real Supabase-backed `DATABASE_URL` from `.env`) and the app run with `flutter run -d chrome --dart-define=...` (see README for the full command) pointed at it:
1. Log in with a confirmed test account.
2. Navigate to the Categories screen (there's no nav entry yet until Task 8 — for this checkpoint, temporarily set `home:` in `main.dart` to `const CategoryListScreen()` to reach it directly, then revert before committing).
3. Confirm the 7 default categories appear.
4. Tap "+", create a custom expense category named "Gym" with essential off, save, confirm it appears in the list.
5. Toggle its essential switch on, confirm it stays on after a screen refresh (re-navigate away and back).
6. Tap its archive button, confirm it disappears from the list.

Revert the temporary `main.dart` change (Task 8 replaces it properly with real navigation) before committing.

- [ ] **Step 8: Commit**

```bash
git add frontend/money_tracker_app/lib/features/categories frontend/money_tracker_app/test/features/categories
git commit -m "feat: add category management screens"
```

---

## Task 7: Frontend dashboard model, provider, and screen

**Files:**
- Create: `frontend/money_tracker_app/lib/features/dashboard/models/monthly_summary.dart`
- Create: `frontend/money_tracker_app/lib/features/dashboard/providers/dashboard_provider.dart`
- Create: `frontend/money_tracker_app/lib/features/dashboard/screens/dashboard_screen.dart`
- Test: `frontend/money_tracker_app/test/features/dashboard/dashboard_screen_test.dart`

**Interfaces:**
- Consumes: `apiClientProvider` (M1).
- Produces: `MonthlySummary`, `CategoryBreakdown`, `monthlySummaryProvider` (`FutureProvider<MonthlySummary>`, GETs `/summary`), `DashboardScreen` widget.

- [ ] **Step 1: Summary models**

`frontend/money_tracker_app/lib/features/dashboard/models/monthly_summary.dart`:
```dart
class CategoryBreakdown {
  CategoryBreakdown({
    required this.categoryId,
    required this.categoryName,
    required this.type,
    required this.amount,
  });

  final String categoryId;
  final String categoryName;
  final String type;
  final String amount;

  factory CategoryBreakdown.fromJson(Map<String, dynamic> json) => CategoryBreakdown(
        categoryId: json['category_id'] as String,
        categoryName: json['category_name'] as String,
        type: json['type'] as String,
        amount: json['amount'] as String,
      );
}

class MonthlySummary {
  MonthlySummary({
    required this.month,
    required this.totalIncome,
    required this.totalExpense,
    required this.net,
    required this.byCategory,
  });

  final String month;
  final String totalIncome;
  final String totalExpense;
  final String net;
  final List<CategoryBreakdown> byCategory;

  factory MonthlySummary.fromJson(Map<String, dynamic> json) => MonthlySummary(
        month: json['month'] as String,
        totalIncome: json['total_income'] as String,
        totalExpense: json['total_expense'] as String,
        net: json['net'] as String,
        byCategory: (json['by_category'] as List<dynamic>)
            .map((item) => CategoryBreakdown.fromJson(item as Map<String, dynamic>))
            .toList(),
      );
}
```

- [ ] **Step 2: Dashboard provider**

`frontend/money_tracker_app/lib/features/dashboard/providers/dashboard_provider.dart`:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../models/monthly_summary.dart';

final monthlySummaryProvider = FutureProvider<MonthlySummary>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/summary');
  return MonthlySummary.fromJson(response.data as Map<String, dynamic>);
});
```

- [ ] **Step 3: Dashboard screen**

`frontend/money_tracker_app/lib/features/dashboard/screens/dashboard_screen.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/monthly_summary.dart';
import '../providers/dashboard_provider.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summaryAsync = ref.watch(monthlySummaryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: summaryAsync.when(
        data: (summary) => ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Text('Income: ${summary.totalIncome}', key: const Key('total_income')),
            Text('Expense: ${summary.totalExpense}', key: const Key('total_expense')),
            Text('Net: ${summary.net}', key: const Key('total_net')),
            const SizedBox(height: 24),
            const Text('By category', style: TextStyle(fontWeight: FontWeight.bold)),
            ...summary.byCategory.map((item) => _BreakdownRow(item: item, summary: summary)),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load summary: $error')),
      ),
    );
  }
}

class _BreakdownRow extends StatelessWidget {
  const _BreakdownRow({required this.item, required this.summary});

  final CategoryBreakdown item;
  final MonthlySummary summary;

  @override
  Widget build(BuildContext context) {
    final maxAmount = summary.byCategory
        .map((e) => double.tryParse(e.amount) ?? 0)
        .fold<double>(0, (max, value) => value > max ? value : max);
    final amount = double.tryParse(item.amount) ?? 0;
    final fraction = maxAmount == 0 ? 0.0 : (amount / maxAmount).clamp(0.0, 1.0);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${item.categoryName} — ${item.amount}'),
          FractionallySizedBox(
            widthFactor: fraction,
            alignment: Alignment.centerLeft,
            child: Container(height: 8, color: Theme.of(context).colorScheme.primary),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4: Write the widget test**

`frontend/money_tracker_app/test/features/dashboard/dashboard_screen_test.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/features/dashboard/models/monthly_summary.dart';
import 'package:money_tracker_app/features/dashboard/providers/dashboard_provider.dart';
import 'package:money_tracker_app/features/dashboard/screens/dashboard_screen.dart';

void main() {
  testWidgets('DashboardScreen renders totals and category breakdown', (tester) async {
    final summary = MonthlySummary(
      month: '2026-09',
      totalIncome: '1000.00',
      totalExpense: '400.00',
      net: '600.00',
      byCategory: [
        CategoryBreakdown(categoryId: '1', categoryName: 'Food', type: 'expense', amount: '400.00'),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [monthlySummaryProvider.overrideWith((ref) async => summary)],
        child: const MaterialApp(home: DashboardScreen()),
      ),
    );
    await tester.pump();

    expect(find.text('Income: 1000.00'), findsOneWidget);
    expect(find.text('Expense: 400.00'), findsOneWidget);
    expect(find.text('Net: 600.00'), findsOneWidget);
    expect(find.text('Food — 400.00'), findsOneWidget);
  });
}
```

- [ ] **Step 5: Run the frontend tests**

```bash
flutter test test/features/dashboard/
```
Expected: PASS.

- [ ] **Step 6: Manual click-through against the real local backend**

Same setup as Task 6 Step 7 (real backend, real Supabase-backed test account). Temporarily point `main.dart`'s `home:` at `const DashboardScreen()`, add at least one transaction via `curl` (or the existing entry screen) for the current month, reload, and confirm the totals and breakdown match what's in the database. Revert the temporary change before committing (Task 8 wires real navigation).

- [ ] **Step 7: Commit**

```bash
git add frontend/money_tracker_app/lib/features/dashboard frontend/money_tracker_app/test/features/dashboard
git commit -m "feat: add monthly dashboard screen"
```

---

## Task 8: Navigation shell + wire real categories into transaction entry

**Files:**
- Create: `frontend/money_tracker_app/lib/core/home_shell.dart`
- Modify: `frontend/money_tracker_app/lib/features/auth/screens/login_screen.dart`
- Modify: `frontend/money_tracker_app/lib/features/transactions/screens/transaction_entry_screen.dart`
- Modify: `frontend/money_tracker_app/test/features/transactions/transaction_entry_screen_test.dart`

**Interfaces:**
- Consumes: `categoryListProvider` (Task 6), `DashboardScreen` (Task 7), `CategoryListScreen` (Task 6), `TransactionEntryScreen` (M1).
- Produces: `HomeShell` widget — the new post-login landing screen with a 3-tab bottom navigation (Dashboard / Add / Categories).

This closes the M1 placeholder: `TransactionEntryScreen`'s hardcoded `_placeholderCategories` map is replaced with a real fetch, and there's finally a way to reach the two new screens.

- [ ] **Step 1: Write the navigation shell**

`frontend/money_tracker_app/lib/core/home_shell.dart`:
```dart
import 'package:flutter/material.dart';

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
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: Point login at the new shell**

In `frontend/money_tracker_app/lib/features/auth/screens/login_screen.dart`, replace the import and navigation target:
```dart
import '../../../core/home_shell.dart';
```
(replaces `import '../../transactions/screens/transaction_entry_screen.dart';`)

```dart
    ref.listen(authControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const HomeShell()),
        );
      }
    });
```
(only the `builder:` target changes, from `TransactionEntryScreen()` to `HomeShell()`)

- [ ] **Step 3: Replace the placeholder categories in the entry screen**

Rewrite `frontend/money_tracker_app/lib/features/transactions/screens/transaction_entry_screen.dart` (full file):
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
    if (categoryId == null) return;
    final draft = TransactionDraft(
      categoryId: categoryId,
      type: _type,
      amount: _amountController.text,
      occurredOn: _occurredOn.toIso8601String().split('T').first,
      note: _noteController.text,
    );
    ref.read(transactionEntryControllerProvider.notifier).submit(draft);
  }
}
```

- [ ] **Step 4: Update the entry screen's widget test to fake the category fetch**

Rewrite `frontend/money_tracker_app/test/features/transactions/transaction_entry_screen_test.dart` (full file):
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
    Category(id: '1', name: 'Food', type: 'expense', isEssential: true, isArchived: false),
    Category(id: '2', name: 'Salary', type: 'income', isEssential: null, isArchived: false),
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
    expect(find.byKey(const Key('date_field')), findsOneWidget);
    expect(find.byKey(const Key('note_field')), findsOneWidget);
    expect(find.byKey(const Key('submit_button')), findsOneWidget);
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
}
```

- [ ] **Step 5: Run all frontend tests**

```bash
flutter test
flutter analyze
```
Expected: all tests PASS, `flutter analyze` reports no errors.

- [ ] **Step 6: Manual click-through against the real local backend**

With the real local backend and a confirmed test account (same setup as prior tasks' click-throughs, now via the actual app — no more temporary `main.dart` edits needed):
1. Log in, land on the Dashboard tab (shows current month's real totals).
2. Switch to the Add tab, confirm the category dropdown shows real fetched categories (not the old hardcoded 4), save a transaction.
3. Switch back to Dashboard, confirm the new transaction is reflected in the totals and breakdown.
4. Switch to Categories, confirm the list matches what Task 6 already verified.

- [ ] **Step 7: Commit**

```bash
git add frontend/money_tracker_app/lib/core/home_shell.dart frontend/money_tracker_app/lib/features/auth/screens/login_screen.dart frontend/money_tracker_app/lib/features/transactions/screens/transaction_entry_screen.dart frontend/money_tracker_app/test/features/transactions/transaction_entry_screen_test.dart
git commit -m "feat: add navigation shell and wire real categories into transaction entry"
```

---

## Task 9: Full-stack smoke check, real-Supabase click-through, and M2 wrap-up

**Files:**
- No new source files — this is a verification + PM checkpoint task, same shape as M1's Task 10.

- [ ] **Step 1: Run the full backend suite**

```bash
cd backend && source .venv/bin/activate
docker compose -f ../docker-compose.dev.yml up -d
alembic upgrade head
pytest -v
```
Expected: every test from Tasks 1-5 PASSES — 44 total across the whole backend suite (the 23 from M1 plus 7 in `test_category_schemas.py`, 8 in `test_categories_api.py`, 4 in `test_summary_api.py`, and 2 new ownership-check tests added to `test_transactions_api.py` in Task 4).

- [ ] **Step 2: Run the full frontend suite**

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
cd ../frontend/money_tracker_app
flutter test
flutter analyze
```
Expected: all tests PASS, no analyzer errors.

- [ ] **Step 3: End-to-end click-through against the real Supabase project**

Using the app run against a real local `uvicorn` backend (itself pointed at the real Supabase `DATABASE_URL`/`SUPABASE_URL` from `backend/.env`) and a real confirmed Supabase Auth test account:

1. Sign up or log in.
2. On the Categories tab, create a new custom expense category, mark it essential, confirm it appears and the toggle sticks.
3. Archive a different, unused default category; confirm it disappears from the Add-transaction dropdown immediately (re-navigate to the Add tab).
4. On the Add tab, create two expense transactions in the same category and one income transaction, across the current month.
5. On the Dashboard tab, confirm total income, total expense, and net match what was just entered, and the per-category breakdown lists the right amounts.
6. Query the database directly (e.g. via the Supabase SQL editor or an execute_sql call) to confirm the same numbers are actually persisted, not just reflected in client-side state:
   ```sql
   select c.name, t.type, sum(t.amount) from transactions t
   join categories c on c.id = t.category_id
   where t.user_id = '<test user's UUID>'
   group by c.name, t.type;
   ```

- [ ] **Step 4: PM checkpoint — do not start M3**

Summarize for the user: what was built (per-user category CRUD with archive-only removal, monthly summary endpoint, category management UI, monthly dashboard, navigation shell), what's confirmed working end to end against the real Supabase project, and confirm scope for M3 (`Budget suggestion endpoint (cold-start + 3-month engine, essentials/discretionary split)` / `Budget input (cold-start), budget display/edit UI` per `02_agent_structure.md`'s milestone table) before proceeding. Note explicitly that this plan did not touch Render — the M2 backend changes still need a `git push` and Render will auto-deploy them (Render's `autoDeploy: true`), so the Render click-through from the Supabase/Render setup plan's pattern should be repeated once M2 is pushed, the same way it was for M1.

---

## Self-Review Notes

- **Spec coverage:** Per-user categories with archive-only removal (Task 1), category CRUD API (Task 3), essential-only-for-expense validation (Tasks 2 and 3), transaction category-ownership fix (Task 4), single-month summary endpoint with no month-over-month/3-month comparison (Task 5), category management UI (Task 6), monthly dashboard (Task 7), navigation shell and closing the M1 placeholder (Task 8), manual click-through after each frontend feature plus a final real-Supabase pass (Tasks 6-9) — every spec section maps to a task.
- **Migration data loss confirmed with the user:** Task 1's migration deletes the 7 M1-seeded categories and the 2 test transactions referencing them, per the design doc's explicit call-out (approved in brainstorming).
- **Type consistency checked:** `Category.user_id`/`is_archived` (Task 1) match the fields `CategoryRead`/`CategoryUpdate` (Task 2) and `app.services.categories` (Task 3) read/write. `get_category(db, user_id, category_id) -> Category | None` (Task 3) is the exact signature Task 4's ownership check calls. `MonthlySummary`/`CategoryBreakdownItem` field names (Task 5) match exactly what the frontend's `MonthlySummary`/`CategoryBreakdown.fromJson` (Task 7) parse. `Category.fromJson`'s field names (Task 6) match `CategoryRead`'s JSON output (Task 2) exactly (`is_essential`, `is_archived`).
- **No out-of-scope work:** no hard delete, no un-archiving, no charting library, no transaction history/list screen, no month-over-month comparison — all explicitly deferred per the design doc's "Out of scope for M2" section.
