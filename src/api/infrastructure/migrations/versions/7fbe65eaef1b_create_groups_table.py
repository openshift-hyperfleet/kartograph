"""create groups table

Revision ID: 7fbe65eaef1b
Revises:
Create Date: 2025-12-23 14:51:40.833197

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7fbe65eaef1b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "groups",
        sa.Column("id", sa.String(length=26), nullable=False),  # ULID
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),  # ULID
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_groups_workspace_id"), "groups", ["workspace_id"], unique=False
    )
    # Ensure group names are unique within each workspace
    op.create_index(
        op.f("ix_groups_workspace_id_name"),
        "groups",
        ["workspace_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_groups_workspace_id_name"), table_name="groups")
    op.drop_index(op.f("ix_groups_workspace_id"), table_name="groups")
    op.drop_table("groups")
