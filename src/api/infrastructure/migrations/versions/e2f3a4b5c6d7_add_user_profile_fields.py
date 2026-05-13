"""add name and email columns to users table

Expand user profile storage for JIT provisioning. The name and email
claims are extracted from OIDC tokens on each login and synced to the
local user record.

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
Create Date: 2026-05-12 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add name and email nullable columns to users table."""
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove name and email columns from users table."""
    op.drop_column("users", "email")
    op.drop_column("users", "name")
