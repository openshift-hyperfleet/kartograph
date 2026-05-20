"""add commit reference columns to data_sources

Adds commit reference tracking fields for Git-backed data sources:
- clone_head_commit
- last_extraction_baseline_commit
- tracked_branch_head_commit

Revision ID: f8e9f0a1b2c3
Revises: f7d8e9f0a1b2
Create Date: 2026-05-14 16:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "f7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable commit-reference columns to data_sources."""
    op.add_column(
        "data_sources",
        sa.Column("clone_head_commit", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "data_sources",
        sa.Column("last_extraction_baseline_commit", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "data_sources",
        sa.Column("tracked_branch_head_commit", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Drop commit-reference columns from data_sources."""
    op.drop_column("data_sources", "tracked_branch_head_commit")
    op.drop_column("data_sources", "last_extraction_baseline_commit")
    op.drop_column("data_sources", "clone_head_commit")

