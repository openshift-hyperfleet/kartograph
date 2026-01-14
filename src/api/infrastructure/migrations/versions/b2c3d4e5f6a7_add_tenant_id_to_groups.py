"""add_tenant_id_to_groups

Add tenant_id column to the groups table. This makes the Group aggregate
self-contained per DDD principles - the aggregate knows which tenant it
belongs to rather than relying on external context.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-09 10:01:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tenant_id column to groups table."""
    op.add_column(
        "groups",
        sa.Column(
            "tenant_id",
            sa.String(length=26),  # ULID length
            nullable=False,
            # No server_default - existing rows need to be handled
        ),
    )

    # Add index for efficient tenant-scoped queries
    op.create_index(
        "idx_groups_tenant_id",
        "groups",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove tenant_id column from groups table."""
    op.drop_index("idx_groups_tenant_id", table_name="groups")
    op.drop_column("groups", "tenant_id")
