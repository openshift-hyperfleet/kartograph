"""Add knowledge-graph maintenance schedule and run history columns.

Revision ID: fa0b1c2d3e4f
Revises: f8e9f0a1b2c3
Create Date: 2026-05-14 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fa0b1c2d3e4f"
down_revision = "f8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add maintenance schedule and run history JSONB columns."""
    op.add_column(
        "knowledge_graphs",
        sa.Column(
            "maintenance_schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "knowledge_graphs",
        sa.Column(
            "maintenance_run_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("knowledge_graphs", "maintenance_run_history", server_default=None)


def downgrade() -> None:
    """Remove maintenance schedule and run history columns."""
    op.drop_column("knowledge_graphs", "maintenance_run_history")
    op.drop_column("knowledge_graphs", "maintenance_schedule")
