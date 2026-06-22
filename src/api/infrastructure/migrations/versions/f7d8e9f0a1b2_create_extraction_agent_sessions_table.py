"""create extraction_agent_sessions table

Stores per-user/per-knowledge-graph/per-mode extraction sessions, including
chat history, runtime context, and archival timestamps used by Clear chat.

Revision ID: f7d8e9f0a1b2
Revises: f6c7d8e9f0a1
Create Date: 2026-05-14 15:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "f6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create extraction session table and scope indexes."""
    op.create_table(
        "extraction_agent_sessions",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("knowledge_graph_id", sa.String(length=26), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column(
            "message_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "runtime_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('schema_bootstrap', 'extraction_operations')",
            name="ck_extract_sessions_mode",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_extract_sessions_scope_active",
        "extraction_agent_sessions",
        ["user_id", "knowledge_graph_id", "mode", "archived_at"],
    )
    op.create_index(
        "idx_extract_sessions_scope_updated",
        "extraction_agent_sessions",
        ["user_id", "knowledge_graph_id", "updated_at"],
    )


def downgrade() -> None:
    """Drop extraction session table and indexes."""
    op.drop_index(
        "idx_extract_sessions_scope_updated", table_name="extraction_agent_sessions"
    )
    op.drop_index(
        "idx_extract_sessions_scope_active", table_name="extraction_agent_sessions"
    )
    op.drop_table("extraction_agent_sessions")
