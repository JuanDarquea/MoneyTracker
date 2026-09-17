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

    budget_source = postgresql.ENUM("computed", "manual", name="budget_source")
    budget_source.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("is_essential", sa.Boolean(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        # create_type=False: the type is created explicitly above (checkfirst=True);
        # without this, SQLAlchemy's own DDL-event auto-creation for native enum
        # columns tries to CREATE TYPE again while compiling this CREATE TABLE and
        # raises "type already exists" on a real Postgres backend (not caught by
        # the ORM-metadata-driven test suite, only by actually running the migration).
        sa.Column("source", postgresql.ENUM("computed", "manual", name="budget_source", create_type=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "category_id", "is_essential", name="uq_budgets_user_category_essential"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_budgets_user_id", table_name="budgets")
    op.drop_table("budgets")
    postgresql.ENUM(name="budget_source").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_income_targets_user_id", table_name="income_targets")
    op.drop_table("income_targets")
