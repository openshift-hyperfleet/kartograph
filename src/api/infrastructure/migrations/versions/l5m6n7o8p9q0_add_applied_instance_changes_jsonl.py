"""Add applied instance change snapshots to extraction jobs.

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, Sequence[str], None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extraction_jobs",
        sa.Column("applied_instance_changes_jsonl", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("extraction_jobs", "applied_instance_changes_jsonl")
