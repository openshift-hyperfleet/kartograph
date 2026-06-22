"""Add graph_management_ui_mode to extraction agent sessions.

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, Sequence[str], None] = "j3k4l5m6n7o8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extraction_agent_sessions",
        sa.Column("graph_management_ui_mode", sa.String(length=64), nullable=True),
    )
    op.execute(
        """
        UPDATE extraction_agent_sessions
        SET graph_management_ui_mode = COALESCE(
            runtime_context->>'graph_management_ui_mode',
            CASE mode
                WHEN 'schema_bootstrap' THEN 'initial-schema-design'
                ELSE 'extraction-jobs'
            END
        )
        """
    )
    op.create_index(
        "idx_extract_sessions_ui_mode_active",
        "extraction_agent_sessions",
        ["user_id", "knowledge_graph_id", "graph_management_ui_mode", "archived_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_extract_sessions_ui_mode_active", table_name="extraction_agent_sessions"
    )
    op.drop_column("extraction_agent_sessions", "graph_management_ui_mode")
