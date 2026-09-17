import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Category, CategoryType

test_engine = create_engine(get_settings().test_database_url)
TestSessionLocal = sessionmaker(bind=test_engine)


@pytest.fixture()
def client(db: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


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
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


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
