import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.models import Category, CategoryType

test_engine = create_engine(get_settings().database_url)
TestSessionLocal = sessionmaker(bind=test_engine)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


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
