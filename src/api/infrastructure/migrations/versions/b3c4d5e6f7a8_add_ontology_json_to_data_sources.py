"""add ontology_json to data_sources

Adds a nullable JSONB column `ontology_json` to the `data_sources` table to
store the approved ontology (node types, edge types, and their properties)
for a data source.

An empty/null ontology is valid — data sources will start with NULL and
gain an ontology after the agent-proposal approval step in the UI.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable ontology_json JSONB column to data_sources."""
    op.add_column(
        "data_sources",
        sa.Column("ontology_json", JSONB, nullable=True),
    )


def downgrade() -> None:
    """Remove ontology_json column from data_sources."""
    op.drop_column("data_sources", "ontology_json")
