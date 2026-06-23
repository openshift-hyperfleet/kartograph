"""add prepared commit and file count columns to data_sources

Tracks the commit SHA and file count captured during the last ingest-only
prepare run so the UI can show branch freshness and JobPackage scope.

Revision ID: g9h0i1j2k3l4
Revises: fc2d3e4f5a6b
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g9h0i1j2k3l4"
down_revision: Union[str, Sequence[str], None] = "fc2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_sources",
        sa.Column("last_prepared_commit", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "data_sources",
        sa.Column("last_prepared_file_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("data_sources", "last_prepared_file_count")
    op.drop_column("data_sources", "last_prepared_commit")
