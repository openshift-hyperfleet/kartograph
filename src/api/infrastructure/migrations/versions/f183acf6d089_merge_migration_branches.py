"""merge migration branches

Revision ID: f183acf6d089
Revises: d5e6f7a8b9c0, e1f2a3b4c5d6
Create Date: 2026-04-30 21:09:35.028670

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f183acf6d089"
down_revision: Union[str, Sequence[str], None] = ("d5e6f7a8b9c0", "e1f2a3b4c5d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
