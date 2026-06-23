"""Add target_files column to extraction_jobs.

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "i2j3k4l5m6n7"
down_revision: Union[str, Sequence[str], None] = "h1i2j3k4l5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extraction_jobs",
        sa.Column("target_files", JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("extraction_jobs", "target_files")
