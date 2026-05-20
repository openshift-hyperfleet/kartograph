"""add mutation_log_run metadata column to data_source_sync_runs

Stores run-level mutation log metadata used by extraction/graph lifecycle
tracking (session, actor, timestamps, token/cost totals, operation counts).

Revision ID: f6c7d8e9f0a1
Revises: f5b6c7d8e9f0
Create Date: 2026-05-14 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "f5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable JSONB mutation log run metadata column."""
    op.add_column(
        "data_source_sync_runs",
        sa.Column("mutation_log_run", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Drop mutation log run metadata column."""
    op.drop_column("data_source_sync_runs", "mutation_log_run")
