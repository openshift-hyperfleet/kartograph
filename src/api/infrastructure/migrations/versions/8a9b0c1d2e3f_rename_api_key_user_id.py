"""rename api_key user_id to created_by_user_id

Revision ID: 8a9b0c1d2e3f
Revises: 7f8e6d19b187
Create Date: 2026-01-22

Renames the user_id column to created_by_user_id to clarify that this
is for audit trail (who created the key) rather than authorization.
Authorization (owner relationship) is handled by SpiceDB.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8a9b0c1d2e3f"
down_revision: Union[str, Sequence[str], None] = "7f8e6d19b187"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename user_id column to created_by_user_id."""
    # Rename the column
    op.alter_column(
        "api_keys",
        "user_id",
        new_column_name="created_by_user_id",
    )

    # Rename the composite index
    op.drop_index("ix_api_keys_tenant_id_user_id", table_name="api_keys")
    op.create_index(
        "ix_api_keys_tenant_id_created_by_user_id",
        "api_keys",
        ["tenant_id", "created_by_user_id"],
    )

    # Note: The unique constraint name stays the same (uq_api_keys_tenant_user_name)
    # as it's just a name and the constraint still references the same columns
    # (now with the new column name)


def downgrade() -> None:
    """Rename created_by_user_id column back to user_id."""
    # Rename the composite index back
    op.drop_index("ix_api_keys_tenant_id_created_by_user_id", table_name="api_keys")
    op.create_index(
        "ix_api_keys_tenant_id_user_id",
        "api_keys",
        ["tenant_id", "user_id"],
    )

    # Rename the column back
    op.alter_column(
        "api_keys",
        "created_by_user_id",
        new_column_name="user_id",
    )
