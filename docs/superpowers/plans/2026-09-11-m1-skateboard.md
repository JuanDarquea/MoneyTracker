# M1 — Skateboard (Auth + Transaction CRUD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the MoneyTracker repo (FastAPI backend + Flutter app, Supabase-backed) and deliver Milestone 1 from `Planning/02_agent_structure.md`: Supabase Auth wiring + basic transaction CRUD on the backend, auth screens + transaction entry on the frontend — with Backend publishing the API contract early so Frontend isn't blocked.

**Architecture:** FastAPI backend (async, Pydantic v2, SQLAlchemy 2.0, Alembic) talking to Postgres (local Docker container standing in for Supabase Postgres during dev; same schema Supabase will host in staging/prod) and verifying Supabase Auth JWTs. Flutter app (single codebase, Riverpod state management) with a thin API client generated against the backend's published OpenAPI contract, using `supabase_flutter` for auth.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Postgres 16 (Docker for dev, Supabase for staging/prod), PyJWT, pytest + httpx. Flutter 3.47 (stable, installed at `~/development/flutter`), Riverpod, `supabase_flutter`, `dio`.

## Global Constraints

- All money fields use `Decimal` end to end — Postgres `NUMERIC`, Python `Decimal`, never `float` (`01_project_outline.md` §7, §9 row 4).
- Backend framework is FastAPI with Pydantic validation (`01_project_outline.md` §9 row 4).
- Database is PostgreSQL, hosted on Supabase in staging/prod (`01_project_outline.md` §9 row 3).
- Auth is Supabase Auth — verify JWTs, don't roll custom auth (`01_project_outline.md` §9 row 2).
- Frontend is Flutter, one codebase for mobile + web (`01_project_outline.md` §9 row 1).
- State management is Riverpod (`02_agent_structure.md` Frontend deliverables).
- Online-only for MVP — no offline queue/sync logic (`01_project_outline.md` §9 row 6).
- Single-user scope — no shared/family account logic (`01_project_outline.md` §3).
- Calendar-month tracking, not pay-cycle-aligned (`01_project_outline.md` §4.5).
- API-contract-first: Backend publishes endpoint shapes before full business logic lands so Frontend can build against stubs (`02_agent_structure.md` §4).
- Quick transaction entry is a product goal: < 10 seconds, ≤ 4 taps (`01_project_outline.md` §2; `02_agent_structure.md` Frontend deliverables). Keep the entry form to exactly: amount, type, category, date (defaulted to today), optional note.
- Backend business-logic test coverage target is 90%+ (`03_testing_strategy.md` §6) — applies here to the transaction CRUD service and Decimal handling, not to wiring/boilerplate.
- M1 scope is strictly: Backend = auth wiring + basic transaction CRUD. Frontend = auth screens + transaction entry. Category CRUD, monthly summaries, dashboards, and the budget engine are M2/M3 — do not build them now even though `categories`/`budgets` tables are mentioned as overall Backend Agent deliverables in `02_agent_structure.md` §3; only a minimal seeded `categories` table (no CRUD endpoints) is in scope here, just enough for transactions to reference a valid category.
- No real Supabase or Render account creation in this plan — that requires the user's own account (Claude does not create third-party accounts). Backend is built against a local Docker Postgres with the same schema, and Supabase Auth JWTs are verified via the shared JWT secret pattern (`SUPABASE_JWT_SECRET` env var) so tests are self-contained and don't need a live Supabase project. Wiring to the user's real Supabase project happens by dropping their credentials into `.env` — no code changes needed.

---

## File Structure

```
MoneyTracker/
├── .gitignore
├── README.md
├── docker-compose.dev.yml            # local Postgres 16 for dev/test
├── docs/api/openapi_contract.md      # published contract snapshot (Task 6)
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial_schema.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/{__init__.py, config.py, security.py}
│   │   ├── db/{__init__.py, base.py, session.py}
│   │   ├── models/{__init__.py, category.py, transaction.py}
│   │   ├── schemas/{__init__.py, category.py, transaction.py}
│   │   ├── api/{__init__.py, deps.py, v1/{__init__.py, router.py, health.py, transactions.py}}
│   │   └── services/{__init__.py, transactions.py}
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       ├── test_security.py
│       ├── test_decimal_precision.py
│       └── test_transactions_api.py
└── frontend/money_tracker_app/        # flutter create output
    ├── pubspec.yaml
    ├── lib/
    │   ├── main.dart
    │   ├── core/{env.dart, api_client.dart, supabase_client.dart}
    │   └── features/
    │       ├── auth/{screens/{login_screen.dart, signup_screen.dart}, providers/auth_provider.dart}
    │       └── transactions/{models/transaction.dart, providers/transaction_provider.dart, screens/transaction_entry_screen.dart}
    └── test/
        ├── widget_test.dart
        └── features/transactions/transaction_model_test.dart
```

---

## Task 1: Repo skeleton, backend project scaffold, health endpoint

**Files:**
- Create: `.gitignore`, `README.md`, `docker-compose.dev.yml`
- Create: `backend/requirements.txt`, `backend/.env.example`
- Create: `backend/app/__init__.py`, `backend/app/main.py`
- Create: `backend/app/core/__init__.py`, `backend/app/core/config.py`
- Create: `backend/app/api/__init__.py`, `backend/app/api/v1/__init__.py`, `backend/app/api/v1/router.py`, `backend/app/api/v1/health.py`
- Create: `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.core.config.Settings` (pydantic-settings, reads `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_JWT_AUD` from env, exposes a `get_settings()` cached accessor). `app.main.app` — the FastAPI instance, with the v1 router mounted at `/api/v1`. `GET /api/v1/health` → `{"status": "ok"}`.

- [ ] **Step 1: Create repo root files**

`.gitignore`:
```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/

# Env / secrets
.env
*.env.local

# Flutter/Dart
frontend/money_tracker_app/.dart_tool/
frontend/money_tracker_app/.flutter-plugins
frontend/money_tracker_app/.flutter-plugins-dependencies
frontend/money_tracker_app/build/
frontend/money_tracker_app/.pub-cache/
frontend/money_tracker_app/**/generated_plugin_registrant.dart

# IDE / OS
.vscode/
.idea/
.DS_Store
```

`README.md`:
```markdown
# MoneyTracker

Personal finance tracker (mobile + web). See `Planning/` for the full
product spec, agent structure, testing strategy, and production plan.

## Backend (FastAPI)

    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # fill in DATABASE_URL / SUPABASE_JWT_SECRET
    docker compose -f ../docker-compose.dev.yml up -d
    alembic upgrade head
    uvicorn app.main:app --reload

## Frontend (Flutter)

    cd frontend/money_tracker_app
    flutter pub get
    flutter run -d web-server   # or -d linux, once a device is available
```

`docker-compose.dev.yml`:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: moneytracker
      POSTGRES_PASSWORD: moneytracker
      POSTGRES_DB: moneytracker
    ports:
      - "5433:5432"
    volumes:
      - moneytracker_pg_data:/var/lib/postgresql/data

volumes:
  moneytracker_pg_data:
```

- [ ] **Step 2: Backend dependency + env files**

`backend/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
pydantic-settings==2.7.0
sqlalchemy==2.0.36
alembic==1.14.0
psycopg[binary]==3.2.3
pyjwt==2.10.1
python-dotenv==1.0.1
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.28.1
```

`backend/.env.example`:
```
DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker
SUPABASE_JWT_SECRET=dev-only-change-me
SUPABASE_JWT_AUD=authenticated
```

- [ ] **Step 3: `app/core/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker"
    supabase_jwt_secret: str = "dev-only-change-me"
    supabase_jwt_aud: str = "authenticated"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Health endpoint + app wiring**

`backend/app/api/v1/health.py`:
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`backend/app/api/v1/router.py`:
```python
from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
```

`backend/app/main.py`:
```python
from fastapi import FastAPI

from app.api.v1.router import api_router

app = FastAPI(title="MoneyTracker API", version="0.1.0")
app.include_router(api_router, prefix="/api/v1")
```

- [ ] **Step 5: Write the health check test**

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
```

`backend/tests/test_health.py`:
```python
def test_health_returns_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 6: Install deps and run the test**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest tests/test_health.py -v
```
Expected: `test_health_returns_ok PASSED`

- [ ] **Step 7: Init git repo and commit**

```bash
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker
git init
git add .gitignore README.md docker-compose.dev.yml backend/requirements.txt backend/.env.example backend/app backend/tests Planning
git commit -m "chore: scaffold repo and FastAPI backend with health endpoint"
```

---

## Task 2: Database models, migration, seeded categories

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/session.py`
- Create: `backend/app/models/__init__.py`, `backend/app/models/category.py`, `backend/app/models/transaction.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial_schema.py`
- Modify: `backend/tests/conftest.py` (add DB fixtures)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.core.config.get_settings()` from Task 1.
- Produces: `app.db.base.Base` (SQLAlchemy declarative base), `app.db.session.get_db()` (FastAPI dependency yielding a `Session`), `app.models.category.Category` (`id: UUID`, `name: str`, `type: CategoryType`, `is_essential: bool | None`), `app.models.transaction.Transaction` (`id: UUID`, `user_id: UUID`, `category_id: UUID`, `type: TransactionType`, `amount: Decimal`, `occurred_on: date`, `note: str | None`, `created_at`, `updated_at`). `CategoryType` / `TransactionType` are `str` enums with values `"income"` / `"expense"`.

- [ ] **Step 1: `app/db/base.py` and `app/db/session.py`**

```python
# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```python
# backend/app/db/session.py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Models**

```python
# backend/app/models/category.py
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
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[CategoryType] = mapped_column(Enum(CategoryType, name="category_type"), nullable=False)
    is_essential: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
```

```python
# backend/app/models/transaction.py
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Date, func
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
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, name="transaction_type"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

`backend/app/models/__init__.py`:
```python
from app.models.category import Category, CategoryType
from app.models.transaction import Transaction, TransactionType

__all__ = ["Category", "CategoryType", "Transaction", "TransactionType"]
```

- [ ] **Step 3: Alembic setup + initial migration with seed data**

```bash
cd backend
alembic init alembic
```

Edit `backend/alembic/env.py` — replace the `target_metadata = None` line and add imports near the top:
```python
from app.core.config import get_settings
from app.db.base import Base
from app.models import Category, Transaction  # noqa: F401 - ensures models are registered

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
```

`backend/alembic/versions/0001_initial_schema.py`:
```python
"""initial schema: categories, transactions

Revision ID: 0001
Revises:
Create Date: 2026-09-11
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

category_type = postgresql.ENUM("income", "expense", name="category_type")
transaction_type = postgresql.ENUM("income", "expense", name="transaction_type")

DEFAULT_CATEGORIES = [
    ("Salary", "income", None),
    ("Food", "expense", True),
    ("Transport", "expense", True),
    ("Housing", "expense", True),
    ("Utilities", "expense", True),
    ("Entertainment", "expense", False),
    ("Shopping", "expense", False),
]


def upgrade() -> None:
    category_type.create(op.get_bind(), checkfirst=True)
    transaction_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("type", category_type, nullable=False),
        sa.Column("is_essential", sa.Boolean(), nullable=True),
    )
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.String(280), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])

    categories_table = sa.table(
        "categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("type", category_type),
        sa.column("is_essential", sa.Boolean),
    )
    op.bulk_insert(
        categories_table,
        [
            {"id": uuid.uuid4(), "name": name, "type": cat_type, "is_essential": essential}
            for name, cat_type, essential in DEFAULT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("categories")
    transaction_type.drop(op.get_bind(), checkfirst=True)
    category_type.drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 4: DB test fixtures**

Add to `backend/tests/conftest.py`:
```python
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import Category, CategoryType

test_engine = create_engine(get_settings().database_url)
TestSessionLocal = sessionmaker(bind=test_engine)


@pytest.fixture()
def db() -> Session:
    Base.metadata.create_all(test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(test_engine)


@pytest.fixture()
def seeded_category(db: Session) -> Category:
    category = Category(id=uuid.uuid4(), name="Food", type=CategoryType.EXPENSE, is_essential=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
```

- [ ] **Step 5: Write the model test**

`backend/tests/test_models.py`:
```python
import uuid
from datetime import date
from decimal import Decimal

from app.models import Transaction, TransactionType


def test_transaction_stores_amount_as_decimal(db, seeded_category):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        category_id=seeded_category.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("12.50"),
        occurred_on=date(2026, 9, 1),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    assert isinstance(txn.amount, Decimal)
    assert txn.amount == Decimal("12.50")
```

- [ ] **Step 6: Run migration against local Postgres, then run the test**

```bash
docker compose -f ../docker-compose.dev.yml up -d
cd backend && source .venv/bin/activate
alembic upgrade head
pytest tests/test_models.py -v
```
Expected: `test_transaction_stores_amount_as_decimal PASSED`

- [ ] **Step 7: Commit**

```bash
git add backend/app/db backend/app/models backend/alembic backend/alembic.ini backend/tests
git commit -m "feat: add categories/transactions schema, migration, and seed data"
```

---

## Task 3: Supabase Auth JWT verification dependency

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/api/deps.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `app.core.config.get_settings()`.
- Produces: `app.core.security.decode_supabase_jwt(token: str) -> dict` (raises `app.core.security.InvalidTokenError` on failure). `app.api.deps.get_current_user_id(authorization: str = Header(...)) -> uuid.UUID` — FastAPI dependency used by every protected route; raises `HTTPException(401)` on a missing/invalid/expired token.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_security.py`:
```python
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import InvalidTokenError, decode_supabase_jwt
from app.api.deps import get_current_user_id


def _make_token(sub: str, aud: str = "authenticated", exp_delta: timedelta = timedelta(hours=1)) -> str:
    settings = get_settings()
    payload = {
        "sub": sub,
        "aud": aud,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def test_decode_valid_token_returns_payload():
    user_id = str(uuid.uuid4())
    token = _make_token(user_id)

    payload = decode_supabase_jwt(token)

    assert payload["sub"] == user_id


def test_decode_expired_token_raises():
    token = _make_token(str(uuid.uuid4()), exp_delta=timedelta(hours=-1))

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_decode_wrong_audience_raises():
    token = _make_token(str(uuid.uuid4()), aud="other-app")

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_get_current_user_id_returns_uuid_for_valid_bearer_header():
    user_id = uuid.uuid4()
    token = _make_token(str(user_id))

    result = get_current_user_id(authorization=f"Bearer {token}")

    assert result == user_id


def test_get_current_user_id_rejects_missing_header():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(authorization=None)

    assert exc_info.value.status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && source .venv/bin/activate
pytest tests/test_security.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.core.security'` (and `app.api.deps`).

- [ ] **Step 3: Implement**

`backend/app/core/security.py`:
```python
import jwt

from app.core.config import get_settings


class InvalidTokenError(Exception):
    pass


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_aud,
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
```

`backend/app/api/deps.py`:
```python
import uuid

from fastapi import Header, HTTPException, status

from app.core.security import InvalidTokenError, decode_supabase_jwt


def get_current_user_id(authorization: str | None = Header(default=None)) -> uuid.UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_supabase_jwt(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    return uuid.UUID(payload["sub"])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_security.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/app/api/deps.py backend/tests/test_security.py
git commit -m "feat: verify Supabase Auth JWTs via shared secret"
```

---

## Task 4: Transaction Pydantic schemas (Decimal-safe)

**Files:**
- Create: `backend/app/schemas/__init__.py`, `backend/app/schemas/transaction.py`
- Test: `backend/tests/test_decimal_precision.py`

**Interfaces:**
- Produces: `app.schemas.transaction.TransactionCreate` (`category_id: UUID`, `type: TransactionType`, `amount: Decimal`, `occurred_on: date`, `note: str | None = None`), `TransactionUpdate` (all fields optional), `TransactionRead` (adds `id`, `user_id`, `created_at`, `updated_at`). Amount is validated as `> 0` and rejects more than 2 decimal places.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_decimal_precision.py`:
```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import TransactionType
from app.schemas.transaction import TransactionCreate


def test_amount_is_decimal_not_float():
    payload = TransactionCreate(
        category_id="11111111-1111-1111-1111-111111111111",
        type=TransactionType.EXPENSE,
        amount="19.99",
        occurred_on="2026-09-01",
    )
    assert isinstance(payload.amount, Decimal)
    assert payload.amount == Decimal("19.99")


def test_amount_rejects_more_than_two_decimal_places():
    with pytest.raises(ValidationError):
        TransactionCreate(
            category_id="11111111-1111-1111-1111-111111111111",
            type=TransactionType.EXPENSE,
            amount="19.995",
            occurred_on="2026-09-01",
        )


def test_amount_must_be_positive():
    with pytest.raises(ValidationError):
        TransactionCreate(
            category_id="11111111-1111-1111-1111-111111111111",
            type=TransactionType.EXPENSE,
            amount="-5.00",
            occurred_on="2026-09-01",
        )
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_decimal_precision.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.schemas'`

- [ ] **Step 3: Implement**

`backend/app/schemas/transaction.py`:
```python
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import TransactionType


class TransactionBase(BaseModel):
    category_id: uuid.UUID
    type: TransactionType
    amount: Decimal
    occurred_on: date
    note: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_is_positive_with_two_decimals(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be greater than zero")
        if value.as_tuple().exponent < -2:
            raise ValueError("amount must have at most 2 decimal places")
        return value


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    type: TransactionType | None = None
    amount: Decimal | None = None
    occurred_on: date | None = None
    note: str | None = None


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

`backend/app/schemas/__init__.py`:
```python
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate

__all__ = ["TransactionCreate", "TransactionRead", "TransactionUpdate"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_decimal_precision.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas backend/tests/test_decimal_precision.py
git commit -m "feat: add Decimal-safe transaction schemas with precision validation"
```

---

## Task 5: Transaction CRUD service + endpoints (auth-protected)

**Files:**
- Create: `backend/app/services/__init__.py`, `backend/app/services/transactions.py`
- Create: `backend/app/api/v1/transactions.py`
- Modify: `backend/app/api/v1/router.py` (register the new router)
- Modify: `backend/tests/conftest.py` (auth header fixture)
- Test: `backend/tests/test_transactions_api.py`

**Interfaces:**
- Consumes: `get_db` (Task 2), `get_current_user_id` (Task 3), `TransactionCreate`/`TransactionUpdate`/`TransactionRead` (Task 4).
- Produces: `app.services.transactions.{create_transaction, list_transactions, get_transaction, update_transaction, delete_transaction}` (all take `db: Session, user_id: UUID, ...`). Routes: `POST /api/v1/transactions`, `GET /api/v1/transactions` (optional `month`, `category_id`, `type` query filters), `GET /api/v1/transactions/{id}`, `PATCH /api/v1/transactions/{id}`, `DELETE /api/v1/transactions/{id}` — all 401 without a valid bearer token, all scoped to the requesting user's `user_id`.

- [ ] **Step 1: Auth header test fixture**

Add to `backend/tests/conftest.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
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
```

Also update the `client` fixture to override `get_db` with the test session:
```python
from app.api.deps import get_db as get_db_dependency  # if get_db lives in deps; otherwise import from app.db.session


@pytest.fixture()
def client(db: Session) -> TestClient:
    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
```
(Remove the old bare `client` fixture from Task 1 — this replaces it.)

- [ ] **Step 2: Write the failing API tests**

`backend/tests/test_transactions_api.py`:
```python
from decimal import Decimal


def test_create_transaction_requires_auth(client, seeded_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "12.50",
            "occurred_on": "2026-09-01",
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
        },
        headers=auth_headers,
    ).json()

    delete_response = client.delete(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 404
```

- [ ] **Step 3: Run to verify failure**

```bash
pytest tests/test_transactions_api.py -v
```
Expected: 404s / `AttributeError` — route and service don't exist yet.

- [ ] **Step 4: Implement service layer**

`backend/app/services/transactions.py`:
```python
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


def create_transaction(db: Session, user_id: uuid.UUID, payload: TransactionCreate) -> Transaction:
    txn = Transaction(id=uuid.uuid4(), user_id=user_id, **payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def list_transactions(db: Session, user_id: uuid.UUID) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.occurred_on.desc())
    return list(db.scalars(stmt))


def get_transaction(db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    return db.scalars(stmt).first()


def update_transaction(db: Session, transaction: Transaction, payload: TransactionUpdate) -> Transaction:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction: Transaction) -> None:
    db.delete(transaction)
    db.commit()
```

- [ ] **Step 5: Implement routes**

`backend/app/api/v1/transactions.py`:
```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services import transactions as transactions_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
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

Update `backend/app/api/v1/router.py`:
```python
from fastapi import APIRouter

from app.api.v1 import health, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(transactions.router)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_transactions_api.py -v
```
Expected: all 5 tests PASS. Then run the full suite to check nothing else broke: `pytest -v`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services backend/app/api/v1/transactions.py backend/app/api/v1/router.py backend/tests
git commit -m "feat: add auth-protected transaction CRUD endpoints"
```

---

## Task 6: Publish the API contract

**Files:**
- Create: `docs/api/openapi_contract.md`
- Create: `backend/scripts/export_openapi.py`

**Interfaces:**
- Produces: `docs/api/openapi_contract.md` — a checked-in snapshot of the current endpoint shapes (paths, request/response schemas) that Frontend builds against. Regenerated by re-running the export script whenever the contract changes.

- [ ] **Step 1: Export script**

`backend/scripts/export_openapi.py`:
```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    schema = app.openapi()
    output_path = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {output_path}")
```

- [ ] **Step 2: Run it and write the human-readable contract doc**

```bash
cd backend && source .venv/bin/activate
python scripts/export_openapi.py
```

`docs/api/openapi_contract.md`:
```markdown
# MoneyTracker API Contract — M1

Machine-readable schema: `docs/api/openapi.json` (regenerate with
`python backend/scripts/export_openapi.py` any time endpoints change).

## Auth

Every endpoint below requires `Authorization: Bearer <supabase-jwt>`.
Missing/invalid/expired token → `401`.

## `POST /api/v1/transactions`

Request body:
```json
{
  "category_id": "uuid",
  "type": "income | expense",
  "amount": "12.50",
  "occurred_on": "2026-09-01",
  "note": "optional string, max 280 chars"
}
```
`amount` is a decimal string, positive, at most 2 decimal places.
Response `201`: `TransactionRead` (adds `id`, `user_id`, `created_at`, `updated_at`).

## `GET /api/v1/transactions`

Response `200`: array of `TransactionRead`, scoped to the caller, newest `occurred_on` first.

## `GET /api/v1/transactions/{id}`

Response `200`: `TransactionRead`. `404` if not found or not owned by caller.

## `PATCH /api/v1/transactions/{id}`

Request body: any subset of the `POST` fields. Response `200`: updated `TransactionRead`.

## `DELETE /api/v1/transactions/{id}`

Response `204`.

## `GET /api/v1/health`

Response `200`: `{"status": "ok"}` — unauthenticated, for uptime checks.

## Not in this contract yet (M2+)

Category CRUD, monthly summary, budget suggestion endpoints — see
`Planning/02_agent_structure.md` milestone table.
```

- [ ] **Step 3: Commit**

```bash
git add docs/api backend/scripts
git commit -m "docs: publish M1 API contract for Frontend"
```

---

## Task 7: Flutter app scaffold (auth + API client shell)

**Files:**
- Create: `frontend/money_tracker_app/` (via `flutter create`)
- Modify: `frontend/money_tracker_app/pubspec.yaml` (add dependencies)
- Create: `frontend/money_tracker_app/lib/core/env.dart`, `lib/core/supabase_client.dart`, `lib/core/api_client.dart`
- Modify: `frontend/money_tracker_app/lib/main.dart`

**Interfaces:**
- Produces: `Env.supabaseUrl` / `Env.supabaseAnonKey` / `Env.apiBaseUrl` (read via `--dart-define`, with dev defaults). `SupabaseClientProvider` — a Riverpod provider exposing the initialized `SupabaseClient`. `ApiClient` (wraps `dio.Dio`, attaches the current Supabase session's access token as a Bearer header, base URL from `Env.apiBaseUrl`).

- [ ] **Step 1: Create the Flutter project**

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker/frontend
flutter create --org com.moneytracker --project-name money_tracker_app money_tracker_app
cd money_tracker_app
flutter test   # confirm the default counter-app test passes before touching anything
```
Expected: default `widget_test.dart` PASSES (proves the toolchain works end to end).

- [ ] **Step 2: Add dependencies**

```bash
flutter pub add flutter_riverpod supabase_flutter dio
```
This updates `pubspec.yaml`/`pubspec.lock` automatically — no manual edits needed.

- [ ] **Step 3: Env + Supabase client**

`lib/core/env.dart`:
```dart
class Env {
  static const supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://your-project.supabase.co',
  );
  static const supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'replace-with-real-anon-key',
  );
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );
}
```

`lib/core/supabase_client.dart`:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'env.dart';

final supabaseClientProvider = Provider<SupabaseClient>((ref) {
  return Supabase.instance.client;
});

Future<void> initSupabase() async {
  await Supabase.initialize(
    url: Env.supabaseUrl,
    anonKey: Env.supabaseAnonKey,
  );
}
```

`lib/core/api_client.dart`:
```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'env.dart';
import 'supabase_client.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(ref.watch(supabaseClientProvider));
});

class ApiClient {
  ApiClient(this._supabase)
      : dio = Dio(BaseOptions(baseUrl: Env.apiBaseUrl)) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = _supabase.auth.currentSession?.accessToken;
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
  }

  final SupabaseClient _supabase;
  final Dio dio;
}
```

- [ ] **Step 4: Wire `main.dart`**

`lib/main.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/supabase_client.dart';
import 'features/auth/screens/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initSupabase();
  runApp(const ProviderScope(child: MoneyTrackerApp()));
}

class MoneyTrackerApp extends StatelessWidget {
  const MoneyTrackerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MoneyTracker',
      theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
      home: const LoginScreen(),
    );
  }
}
```

- [ ] **Step 5: Delete the stock counter widget test (replaced in Task 8)**

```bash
rm test/widget_test.dart
```
(A new `widget_test.dart` is written in Task 8 once `LoginScreen` exists — leaving the old one in place would fail to compile against the new `main.dart`.)

- [ ] **Step 6: Commit**

```bash
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker
git add frontend/money_tracker_app
git commit -m "chore: scaffold Flutter app with Riverpod, Supabase, and API client"
```

---

## Task 8: Auth screens (login + signup)

**Files:**
- Create: `frontend/money_tracker_app/lib/features/auth/providers/auth_provider.dart`
- Create: `frontend/money_tracker_app/lib/features/auth/screens/login_screen.dart`
- Create: `frontend/money_tracker_app/lib/features/auth/screens/signup_screen.dart`
- Test: `frontend/money_tracker_app/test/widget_test.dart`

**Interfaces:**
- Consumes: `supabaseClientProvider` (Task 7).
- Produces: `authControllerProvider` (a `StateNotifierProvider<AuthController, AsyncValue<void>>` exposing `signIn(email, password)` / `signUp(email, password)`). `LoginScreen`, `SignupScreen` widgets — `LoginScreen` has `Key('email_field')`, `Key('password_field')`, `Key('login_button')`, `Key('go_to_signup_link')` for testability.

- [ ] **Step 1: Auth provider**

`lib/features/auth/providers/auth_provider.dart`:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/supabase_client.dart';

final authControllerProvider =
    StateNotifierProvider<AuthController, AsyncValue<void>>((ref) {
  return AuthController(ref.watch(supabaseClientProvider));
});

class AuthController extends StateNotifier<AsyncValue<void>> {
  AuthController(this._supabase) : super(const AsyncData(null));

  final SupabaseClient _supabase;

  Future<void> signIn(String email, String password) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _supabase.auth.signInWithPassword(email: email, password: password),
    );
  }

  Future<void> signUp(String email, String password) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _supabase.auth.signUp(email: email, password: password),
    );
  }
}
```

- [ ] **Step 2: Login screen**

`lib/features/auth/screens/login_screen.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../transactions/screens/transaction_entry_screen.dart';
import '../providers/auth_provider.dart';
import 'signup_screen.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    ref.listen(authControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const TransactionEntryScreen()),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Log in')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              key: const Key('email_field'),
              controller: _emailController,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('password_field'),
              controller: _passwordController,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            if (authState.hasError)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'Login failed: ${authState.error}',
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            ElevatedButton(
              key: const Key('login_button'),
              onPressed: authState.isLoading
                  ? null
                  : () => ref.read(authControllerProvider.notifier).signIn(
                        _emailController.text,
                        _passwordController.text,
                      ),
              child: authState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Log in'),
            ),
            TextButton(
              key: const Key('go_to_signup_link'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SignupScreen()),
              ),
              child: const Text("Don't have an account? Sign up"),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 3: Signup screen**

`lib/features/auth/screens/signup_screen.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/auth_provider.dart';

class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({super.key});

  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends ConsumerState<SignupScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Sign up')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              key: const Key('signup_email_field'),
              controller: _emailController,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('signup_password_field'),
              controller: _passwordController,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            if (authState.hasError)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'Sign up failed: ${authState.error}',
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            ElevatedButton(
              key: const Key('signup_button'),
              onPressed: authState.isLoading
                  ? null
                  : () => ref.read(authControllerProvider.notifier).signUp(
                        _emailController.text,
                        _passwordController.text,
                      ),
              child: authState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Sign up'),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Write the widget test**

`test/widget_test.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/features/auth/screens/login_screen.dart';
import 'package:money_tracker_app/features/auth/screens/signup_screen.dart';

void main() {
  testWidgets('LoginScreen shows email, password, and login button',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: LoginScreen())),
    );

    expect(find.byKey(const Key('email_field')), findsOneWidget);
    expect(find.byKey(const Key('password_field')), findsOneWidget);
    expect(find.byKey(const Key('login_button')), findsOneWidget);
  });

  testWidgets('Tapping "go to signup" navigates to SignupScreen',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: LoginScreen())),
    );

    await tester.tap(find.byKey(const Key('go_to_signup_link')));
    await tester.pumpAndSettle();

    expect(find.byType(SignupScreen), findsOneWidget);
  });
}
```

- [ ] **Step 5: Run the test**

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker/frontend/money_tracker_app
flutter test
```
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker
git add frontend/money_tracker_app
git commit -m "feat: add Supabase Auth login and signup screens"
```

---

## Task 9: Transaction entry screen (against the published contract)

**Files:**
- Create: `frontend/money_tracker_app/lib/features/transactions/models/transaction.dart`
- Create: `frontend/money_tracker_app/lib/features/transactions/providers/transaction_provider.dart`
- Create: `frontend/money_tracker_app/lib/features/transactions/screens/transaction_entry_screen.dart`
- Test: `frontend/money_tracker_app/test/features/transactions/transaction_model_test.dart`
- Test: `frontend/money_tracker_app/test/features/transactions/transaction_entry_screen_test.dart`

**Interfaces:**
- Consumes: `apiClientProvider` (Task 7), the `POST /api/v1/transactions` shape from `docs/api/openapi_contract.md` (Task 6).
- Produces: `TransactionDraft` (`categoryId`, `type`, `amount` as `String` decimal, `occurredOn`, `note`) with `toJson()`. `transactionEntryControllerProvider` (`StateNotifierProvider<TransactionEntryController, AsyncValue<void>>` with `submit(TransactionDraft)` that POSTs via `ApiClient`). `TransactionEntryScreen` — fields keyed `amount_field`, `type_toggle`, `category_dropdown`, `note_field`, `submit_button` (exactly 4 required inputs + optional note, per the ≤4-tap constraint).

- [ ] **Step 1: Model + its test**

`test/features/transactions/transaction_model_test.dart`:
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
}
```

`lib/features/transactions/models/transaction.dart`:
```dart
class TransactionDraft {
  TransactionDraft({
    required this.categoryId,
    required this.type,
    required this.amount,
    required this.occurredOn,
    this.note,
  });

  final String categoryId;
  final String type;
  final String amount;
  final String occurredOn;
  final String? note;

  Map<String, dynamic> toJson() => {
        'category_id': categoryId,
        'type': type,
        'amount': amount,
        'occurred_on': occurredOn,
        if (note != null && note!.isNotEmpty) 'note': note,
      };
}
```

Run: `flutter test test/features/transactions/transaction_model_test.dart` → expect PASS.

- [ ] **Step 2: Entry controller**

`lib/features/transactions/providers/transaction_provider.dart`:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../models/transaction.dart';

final transactionEntryControllerProvider =
    StateNotifierProvider<TransactionEntryController, AsyncValue<void>>((ref) {
  return TransactionEntryController(ref.watch(apiClientProvider));
});

class TransactionEntryController extends StateNotifier<AsyncValue<void>> {
  TransactionEntryController(this._apiClient) : super(const AsyncData(null));

  final ApiClient _apiClient;

  Future<void> submit(TransactionDraft draft) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _apiClient.dio.post('/transactions', data: draft.toJson()),
    );
  }
}
```

- [ ] **Step 3: Entry screen**

`lib/features/transactions/screens/transaction_entry_screen.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/transaction.dart';
import '../providers/transaction_provider.dart';

// M1 ships without category CRUD (M2) — the seeded defaults from the
// backend migration are hardcoded here as a stopgap, matching the ids
// Backend's Task 2 seed inserts in a fixed order won't be stable, so
// this is placeholder UI wiring only: replace with a real category
// fetch once GET /api/v1/categories exists in M2.
const _placeholderCategories = <String>['Food', 'Transport', 'Housing', 'Salary'];

class TransactionEntryScreen extends ConsumerStatefulWidget {
  const TransactionEntryScreen({super.key});

  @override
  ConsumerState<TransactionEntryScreen> createState() => _TransactionEntryScreenState();
}

class _TransactionEntryScreenState extends ConsumerState<TransactionEntryScreen> {
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();
  String _type = 'expense';
  String _category = _placeholderCategories.first;
  DateTime _occurredOn = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final entryState = ref.watch(transactionEntryControllerProvider);

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
              onSelectionChanged: (selection) => setState(() => _type = selection.first),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('amount_field'),
              controller: _amountController,
              decoration: const InputDecoration(labelText: 'Amount'),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 12),
            DropdownButton<String>(
              key: const Key('category_dropdown'),
              value: _category,
              items: _placeholderCategories
                  .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                  .toList(),
              onChanged: (value) => setState(() => _category = value ?? _category),
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

  void _submit() {
    final draft = TransactionDraft(
      categoryId: _category,
      type: _type,
      amount: _amountController.text,
      occurredOn: _occurredOn.toIso8601String().split('T').first,
      note: _noteController.text,
    );
    ref.read(transactionEntryControllerProvider.notifier).submit(draft);
  }
}
```

- [ ] **Step 4: Widget test for the entry screen**

`test/features/transactions/transaction_entry_screen_test.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:money_tracker_app/features/transactions/screens/transaction_entry_screen.dart';

void main() {
  testWidgets('TransactionEntryScreen exposes exactly the required fields', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: TransactionEntryScreen())),
    );

    expect(find.byKey(const Key('amount_field')), findsOneWidget);
    expect(find.byKey(const Key('type_toggle')), findsOneWidget);
    expect(find.byKey(const Key('category_dropdown')), findsOneWidget);
    expect(find.byKey(const Key('note_field')), findsOneWidget);
    expect(find.byKey(const Key('submit_button')), findsOneWidget);
  });
}
```

- [ ] **Step 5: Run all frontend tests**

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker/frontend/money_tracker_app
flutter test
```
Expected: all tests across `test/` PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/juan-darquea/My_Projects/Projects/GitHub/MoneyTracker
git add frontend/money_tracker_app
git commit -m "feat: add transaction entry screen against published API contract"
```

---

## Task 10: Full-stack smoke check + M1 wrap-up

**Files:**
- Modify: `README.md` (fill in the "how to run both halves together" note if anything changed)
- No new source files — this is a verification + PM checkpoint task.

- [ ] **Step 1: Run the full backend suite**

```bash
cd backend && source .venv/bin/activate
docker compose -f ../docker-compose.dev.yml up -d
alembic upgrade head
pytest -v
```
Expected: every test from Tasks 1–5 PASSES.

- [ ] **Step 2: Run the full frontend suite**

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
cd ../frontend/money_tracker_app
flutter test
flutter analyze
```
Expected: all tests PASS, `flutter analyze` reports no errors (warnings about the `_placeholderCategories` TODO are expected and fine).

- [ ] **Step 3: Manual end-to-end smoke check**

```bash
# terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
# terminal 2
curl -s http://localhost:8000/api/v1/health
```
Expected: `{"status":"ok"}`. (Running the Flutter app against the real backend requires the user's real Supabase project credentials in `--dart-define` — flag this as the integration step for the user, not something to fake with placeholder keys.)

- [ ] **Step 4: PM checkpoint — do not start M2**

Summarize for the user (this is the checkpoint the plan stops at): what was built, what's stubbed/placeholder (category dropdown hardcoded, no live Supabase project yet), what needs the user's input before M2 (real Supabase project + Render service creation, since Claude cannot create third-party accounts), and confirm scope for M2 (`Category CRUD, monthly summary endpoint` / `Category management UI, monthly dashboard` per `02_agent_structure.md`'s milestone table) before proceeding.

---

## Self-Review Notes

- **Spec coverage:** Auth wiring (Task 3), basic transaction CRUD (Tasks 2, 4, 5), API-contract-first handoff (Task 6 before Tasks 7–9 touch the frontend), auth screens (Task 8), transaction entry ≤4 required fields (Task 9), Decimal-only money handling (Tasks 2, 4, 9's string-based amount), single-user scoping via `user_id` (Task 5). Category/monthly/budget features are explicitly deferred to M2/M3 per the milestone table — not attempted here.
- **Accounts:** No task creates a Supabase or Render account — Task 3 uses a shared-secret JWT scheme so auth logic is fully testable without one, and Task 10 explicitly calls out that real Supabase credentials are the user's action item before end-to-end use.
- **Type consistency checked:** `get_current_user_id` (Task 3) returns `uuid.UUID`, matching `Transaction.user_id`'s type (Task 2) and the `user_id` param type used throughout `app.services.transactions` (Task 5). `TransactionDraft.amount` and `TransactionCreate.amount` both move as decimal strings across the wire, never as a JSON number, avoiding float round-tripping on the client (Task 9 note is intentional, not an oversight).
