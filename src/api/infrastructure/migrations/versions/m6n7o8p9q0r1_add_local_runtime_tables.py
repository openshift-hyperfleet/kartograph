"""Add local runtime agent presence and work request tables.

Backs the temporary local-Sandbox-execution mode described in
specs/extraction/local-sandbox-execution.spec.md: dispatches Sandbox
lifecycle and chat-turn work to a user's local agent when hosted
OpenShell execution is unavailable.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "m6n7o8p9q0r1"
down_revision: Union[str, Sequence[str], None] = "l5m6n7o8p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "local_runtime_agent_presence",
        sa.Column("user_id", sa.String(length=255), primary_key=True),
        sa.Column("tenant_id", sa.String(length=26), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_local_runtime_presence_tenant",
        "local_runtime_agent_presence",
        ["tenant_id"],
    )

    op.create_table(
        "local_runtime_work_requests",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("tenant_id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("knowledge_graph_id", sa.String(length=26), nullable=False),
        sa.Column("session_id", sa.String(length=26), nullable=True),
        sa.Column("job_id", sa.String(length=26), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("claimed_by_user_id", sa.String(length=255), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "kind IN ('sandbox_start', 'chat_turn', 'sandbox_stop')",
            name="ck_local_runtime_work_requests_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'completed', 'failed')",
            name="ck_local_runtime_work_requests_status",
        ),
    )
    op.create_index(
        "idx_local_runtime_work_requests_user_status",
        "local_runtime_work_requests",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_local_runtime_work_requests_session_status",
        "local_runtime_work_requests",
        ["session_id", "status"],
    )
    op.create_index(
        "idx_local_runtime_work_requests_job_status",
        "local_runtime_work_requests",
        ["job_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_local_runtime_work_requests_job_status",
        table_name="local_runtime_work_requests",
    )
    op.drop_index(
        "idx_local_runtime_work_requests_session_status",
        table_name="local_runtime_work_requests",
    )
    op.drop_index(
        "idx_local_runtime_work_requests_user_status",
        table_name="local_runtime_work_requests",
    )
    op.drop_table("local_runtime_work_requests")
    op.drop_index(
        "idx_local_runtime_presence_tenant",
        table_name="local_runtime_agent_presence",
    )
    op.drop_table("local_runtime_agent_presence")
