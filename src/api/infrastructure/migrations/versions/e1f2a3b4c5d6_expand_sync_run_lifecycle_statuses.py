"""expand sync run lifecycle statuses

Expands the data_source_sync_runs status check constraint to include
the full set of lifecycle states driven by the sync event state machine:
  - pending: initial state when sync run is created
  - ingesting: ingestion pipeline is running (SyncStarted event)
  - ai_extracting: AI entity extraction in progress (JobPackageProduced event)
  - applying: graph mutations being applied (MutationLogProduced event)
  - completed: sync finished successfully (MutationsApplied event)
  - failed: sync failed at any stage (IngestionFailed / ExtractionFailed /
            MutationApplicationFailed events)

Previously only 'pending', 'running', 'completed', 'failed' were allowed.
The 'running' status is replaced by the more specific 'ingesting' state.

Revision ID: e1f2a3b4c5d6
Revises: c4d5e6f7a8b9
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expand the sync run status constraint to support full lifecycle states."""
    # Drop the old constraint
    op.drop_constraint("ck_sync_runs_status", "data_source_sync_runs")

    # Add the new constraint with expanded valid values
    op.create_check_constraint(
        "ck_sync_runs_status",
        "data_source_sync_runs",
        "status IN ('pending', 'ingesting', 'ai_extracting', 'applying', "
        "'completed', 'failed')",
    )


def downgrade() -> None:
    """Revert to the original sync run status constraint."""
    op.drop_constraint("ck_sync_runs_status", "data_source_sync_runs")

    op.create_check_constraint(
        "ck_sync_runs_status",
        "data_source_sync_runs",
        "status IN ('pending', 'running', 'completed', 'failed')",
    )
