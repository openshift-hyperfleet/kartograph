"""Merge migration branches that diverged from f183acf6d089.

Unifies two independent branches that diverged from the common merge point
``f183acf6d089`` after prior parallel development:

  1. Sync-run logs / data-source ontology chain ending at ``b3c4d5e6f7a8``
     (add ontology JSON to data sources via a2b3c4d5e6f7 logs column).
  2. Knowledge-graph ontology chain ending at ``c0d1e2f3a4b5``
     (add ontology JSONB to knowledge_graphs).

After this merge, ``alembic upgrade head`` resolves to a single target.

Revision ID: d0e1f2a3b4c5
Revises: b3c4d5e6f7a8, c0d1e2f3a4b5
Create Date: 2026-05-04 07:40:00.000000

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = (
    "b3c4d5e6f7a8",
    "c0d1e2f3a4b5",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema changes — merge only."""
    pass


def downgrade() -> None:
    """No schema changes — merge only."""
    pass
