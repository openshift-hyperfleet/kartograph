"""create tenants table

Revision ID: e43f566c892b
Revises: d32ecc44581a
Create Date: 2026-01-19 16:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e43f566c892b"
down_revision: Union[str, Sequence[str], None] = "d32ecc44581a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=26), nullable=False),  # ULID
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Ensure tenant names are globally unique
    op.create_index("ix_tenants_name", "tenants", ["name"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tenants_name", table_name="tenants")
    op.drop_table("tenants")
