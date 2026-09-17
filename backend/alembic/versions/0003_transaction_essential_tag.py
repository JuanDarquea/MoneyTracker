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
