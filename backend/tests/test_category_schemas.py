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
