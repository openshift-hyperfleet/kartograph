"""fix workspace parent FK to use RESTRICT

Revision ID: fdd9505854c5
Revises: 2551292512f6
Create Date: 2026-02-10 11:00:14.331984

The parent_workspace_id foreign key should use ON DELETE RESTRICT to prevent
deleting a parent workspace while children exist. This migration ensures the
constraint is correct by dropping and recreating it.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "fdd9505854c5"
down_revision: Union[str, Sequence[str], None] = "2551292512f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix parent_workspace_id FK to use RESTRICT.

    Drops the existing constraint (whatever it may be) and recreates it
    with the correct ON DELETE RESTRICT behavior.
    """
    # Drop existing foreign key constraint
    # The constraint name follows SQLAlchemy's naming convention
    op.drop_constraint(
        "workspaces_parent_workspace_id_fkey",
        "workspaces",
        type_="foreignkey",
    )

    # Recreate with explicit RESTRICT
    op.create_foreign_key(
        "workspaces_parent_workspace_id_fkey",
        "workspaces",
        "workspaces",
        ["parent_workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Revert to previous state (no change needed, RESTRICT is correct)."""
    # No-op: we don't want to revert to a broken state
    pass
