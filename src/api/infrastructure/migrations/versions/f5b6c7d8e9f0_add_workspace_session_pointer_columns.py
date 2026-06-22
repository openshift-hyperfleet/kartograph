"""add workspace session pointer columns to knowledge_graphs

Adds nullable session pointer fields used by workspace status projection
and bootstrap-to-extraction transition commands.

Revision ID: f5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-05-14 13:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workspace session pointer columns."""
    op.add_column(
        "knowledge_graphs",
        sa.Column(
            "active_schema_bootstrap_session_id", sa.String(length=26), nullable=True
        ),
    )
    op.add_column(
        "knowledge_graphs",
        sa.Column(
            "active_extraction_operations_session_id",
            sa.String(length=26),
            nullable=True,
        ),
    )
    op.add_column(
        "knowledge_graphs",
        sa.Column(
            "most_recent_completed_session_id", sa.String(length=26), nullable=True
        ),
    )


def downgrade() -> None:
    """Drop workspace session pointer columns."""
    op.drop_column("knowledge_graphs", "most_recent_completed_session_id")
    op.drop_column("knowledge_graphs", "active_extraction_operations_session_id")
    op.drop_column("knowledge_graphs", "active_schema_bootstrap_session_id")
