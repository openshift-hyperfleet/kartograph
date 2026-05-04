"""Add nullable JSONB ontology column to knowledge_graphs table.

Adds an ``ontology`` JSONB column to store per-KnowledgeGraph ontology
configuration (node types, edge types, approval state).  The column is
nullable so existing rows are unaffected (NULL means no ontology saved).

Revision ID: bba05241205d
Revises: f183acf6d089
Create Date: 2026-05-03 17:34:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "bba05241205d"
down_revision: Union[str, Sequence[str], None] = "f183acf6d089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable JSONB ontology column to knowledge_graphs."""
    op.add_column(
        "knowledge_graphs",
        sa.Column("ontology", JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Remove ontology column from knowledge_graphs."""
    op.drop_column("knowledge_graphs", "ontology")
