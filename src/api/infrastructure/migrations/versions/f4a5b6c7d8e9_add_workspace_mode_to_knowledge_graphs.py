"""add workspace_mode to knowledge_graphs

Adds lifecycle mode tracking to KnowledgeGraph records with a non-null
default of ``schema_bootstrap``.

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-05-14 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workspace_mode with bootstrap default for existing rows."""
    op.add_column(
        "knowledge_graphs",
        sa.Column(
            "workspace_mode",
            sa.String(length=64),
            nullable=False,
            server_default="schema_bootstrap",
        ),
    )


def downgrade() -> None:
    """Drop workspace_mode from knowledge_graphs."""
    op.drop_column("knowledge_graphs", "workspace_mode")
