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
