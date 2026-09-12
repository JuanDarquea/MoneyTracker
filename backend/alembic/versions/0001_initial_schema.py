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

# Separate column-bound references with create_type=False: the enum types are
# created/dropped explicitly below, so create_table must not try to create
# them again (it would otherwise emit a redundant CREATE TYPE and fail with
# DuplicateObject even though checkfirst=True was used above).
category_type_col = postgresql.ENUM("income", "expense", name="category_type", create_type=False)
transaction_type_col = postgresql.ENUM("income", "expense", name="transaction_type", create_type=False)

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
        sa.Column("type", category_type_col, nullable=False),
        sa.Column("is_essential", sa.Boolean(), nullable=True),
    )
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("type", transaction_type_col, nullable=False),
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
            {
                # Deterministic (not random) so the seeded category ids are
                # stable/reproducible across any fresh migration run (dev,
                # test, or a real Supabase project) — the frontend's M1
                # stopgap hardcodes these same ids until M2 adds a real
                # category-fetch endpoint.
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, f"moneytracker.category.{name.lower()}"),
                "name": name,
                "type": cat_type,
                "is_essential": essential,
            }
            for name, cat_type, essential in DEFAULT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("categories")
    transaction_type.drop(op.get_bind(), checkfirst=True)
    category_type.drop(op.get_bind(), checkfirst=True)
