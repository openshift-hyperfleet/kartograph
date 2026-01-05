"""drop workspace_id from groups

Remove workspace_id column from groups table as workspace relationships
are now managed through SpiceDB rather than as a direct column.

Revision ID: 0222e8ddd130
Revises: 7fbe65eaef1b
Create Date: 2026-01-05 11:18:58.708367

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0222e8ddd130"
down_revision: Union[str, Sequence[str], None] = "7fbe65eaef1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop indexes first (must drop before column)
    op.drop_index("ix_groups_workspace_id_name", table_name="groups")
    op.drop_index("ix_groups_workspace_id", table_name="groups")

    # Drop the workspace_id column
    op.drop_column("groups", "workspace_id")

    # Add unique index on name (global uniqueness)
    # Note: Per-tenant uniqueness will be enforced in application logic via SpiceDB
    op.create_index("ix_groups_name", "groups", ["name"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the global unique index
    op.drop_index("ix_groups_name", table_name="groups")

    # Re-add workspace_id column
    op.add_column(
        "groups", sa.Column("workspace_id", sa.String(length=26), nullable=False)
    )

    # Re-create indexes
    op.create_index("ix_groups_workspace_id", "groups", ["workspace_id"], unique=False)
    op.create_index(
        "ix_groups_workspace_id_name", "groups", ["workspace_id", "name"], unique=True
    )
