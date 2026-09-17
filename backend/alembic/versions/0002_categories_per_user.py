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
