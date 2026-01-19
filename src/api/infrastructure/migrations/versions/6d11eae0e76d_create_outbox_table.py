"""create_outbox_table

Create the outbox table for the transactional outbox pattern.
This table stores domain events that need to be processed asynchronously
and applied to SpiceDB for authorization consistency.

Revision ID: 6d11eae0e76d
Revises: d71976bfc705
Create Date: 2026-01-08 13:30:00.318417

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d11eae0e76d"
down_revision: Union[str, Sequence[str], None] = "d71976bfc705"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outbox",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "aggregate_type", sa.String(length=255), nullable=False
        ),  # e.g., "group"
        sa.Column(
            "aggregate_id", sa.String(length=26), nullable=False
        ),  # ULID of aggregate
        sa.Column(
            "event_type", sa.String(length=255), nullable=False
        ),  # e.g., "MemberAdded"
        sa.Column("payload", sa.JSON(), nullable=False),  # Serialized event data
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False
        ),  # When event occurred
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=True
        ),  # NULL until processed
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index for efficiently fetching unprocessed entries ordered by creation time
    op.create_index(
        "idx_outbox_unprocessed",
        "outbox",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("processed_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_outbox_unprocessed", table_name="outbox")
    op.drop_table("outbox")
