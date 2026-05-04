"""add logs column to data_source_sync_runs

Adds a `logs` column to the `data_source_sync_runs` table to store
ordered log lines captured during a sync run. Each log line is a plain
text string (e.g. "2026-04-30T10:00:01Z INFO Starting sync").

The column defaults to an empty array so existing rows are unaffected,
and the UI can render "No log entries for this run." until the Ingestion
and Extraction contexts start populating logs.

Revision ID: a2b3c4d5e6f7
Revises: f183acf6d089
Create Date: 2026-04-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f183acf6d089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add logs column to data_source_sync_runs."""
    op.add_column(
        "data_source_sync_runs",
        sa.Column(
            "logs",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    """Remove logs column from data_source_sync_runs."""
    op.drop_column("data_source_sync_runs", "logs")
