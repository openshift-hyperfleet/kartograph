"""expand_users_id_for_external_sso

Revision ID: 361d2df03685
Revises: f98e5d7623ca
Create Date: 2026-01-20 21:05:59.039254

Expands the users.id column from VARCHAR(26) (ULID-sized) to VARCHAR(255)
to accommodate external SSO user IDs (UUIDs, Auth0 IDs, etc.) per AIHCM-131.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "361d2df03685"
down_revision: Union[str, Sequence[str], None] = "f98e5d7623ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expand users.id column to accommodate external SSO IDs."""
    op.alter_column(
        "users",
        "id",
        existing_type=sa.String(26),
        type_=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert users.id column to ULID size (may truncate data)."""
    op.alter_column(
        "users",
        "id",
        existing_type=sa.String(255),
        type_=sa.String(26),
        existing_nullable=False,
    )
