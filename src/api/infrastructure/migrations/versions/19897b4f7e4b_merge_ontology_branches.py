"""merge_ontology_branches

Revision ID: 19897b4f7e4b
Revises: b3c4d5e6f7a8, bba05241205d
Create Date: 2026-05-04 09:42:23.531924

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "19897b4f7e4b"
down_revision: Union[str, Sequence[str], None] = ("b3c4d5e6f7a8", "bba05241205d")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
