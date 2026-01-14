"""add_outbox_retry_columns

Add retry_count, last_error, and failed_at columns to the outbox table
for dead letter queue functionality. Failed events will be moved to DLQ
after exceeding max retry attempts.

Revision ID: a1b2c3d4e5f6
Revises: d32ecc44581a
Create Date: 2026-01-09 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d32ecc44581a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retry and DLQ columns to outbox table."""
    # Add retry_count column with default 0
    op.add_column(
        "outbox",
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Add last_error column for storing the most recent error message
    op.add_column(
        "outbox",
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
    )

    # Add failed_at column to mark entries that have exceeded retry limit
    op.add_column(
        "outbox",
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create partial index for failed entries (for monitoring/alerting)
    op.create_index(
        "idx_outbox_failed",
        "outbox",
        ["failed_at"],
        unique=False,
        postgresql_where=sa.text("failed_at IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove retry and DLQ columns from outbox table."""
    op.drop_index("idx_outbox_failed", table_name="outbox")
    op.drop_column("outbox", "failed_at")
    op.drop_column("outbox", "last_error")
    op.drop_column("outbox", "retry_count")
