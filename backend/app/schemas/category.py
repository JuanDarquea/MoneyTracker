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
