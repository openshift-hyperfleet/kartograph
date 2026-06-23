"""add ingested sync run status

Adds ``ingested`` as a terminal sync-run status for ingest-only pipeline runs
that prepare ingestion context without AI extraction.

Revision ID: fc2d3e4f5a6b
Revises: fb1c2d3e4f5a
Create Date: 2026-05-26
"""

from typing import Sequence, Union

from alembic import op

revision: str = "fc2d3e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "fb1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_sync_runs_status", "data_source_sync_runs")
    op.create_check_constraint(
        "ck_sync_runs_status",
        "data_source_sync_runs",
        "status IN ('pending', 'ingesting', 'ai_extracting', 'applying', "
        "'ingested', 'completed', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sync_runs_status", "data_source_sync_runs")
    op.create_check_constraint(
        "ck_sync_runs_status",
        "data_source_sync_runs",
        "status IN ('pending', 'ingesting', 'ai_extracting', 'applying', "
        "'completed', 'failed')",
    )
