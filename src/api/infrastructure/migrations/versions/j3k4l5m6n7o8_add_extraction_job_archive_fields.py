"""Add archive and graph-write fields to extraction jobs.

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-06-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, Sequence[str], None] = "i2j3k4l5m6n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extraction_jobs",
        sa.Column(
            "relationships_modified", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "extraction_jobs",
        sa.Column("run_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "extraction_jobs",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "extraction_jobs",
        sa.Column("applied_mutations_jsonl", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extraction_jobs", "applied_mutations_jsonl")
    op.drop_column("extraction_jobs", "archived_at")
    op.drop_column("extraction_jobs", "run_started_at")
    op.drop_column("extraction_jobs", "relationships_modified")
