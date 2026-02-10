"""fix api_keys tenant FK to use RESTRICT

Revision ID: 0c6b5d01f040
Revises: 2551292512f6
Create Date: 2026-02-10 14:11:35.195853

Changes CASCADE to RESTRICT on api_keys.tenant_id FK to force application-level
cascading. This ensures APIKeyDeleted domain events are emitted when API keys are
removed, preventing orphaned SpiceDB relationships.

This aligns api_keys with the pattern already used by groups and workspaces.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0c6b5d01f040"
down_revision: Union[str, Sequence[str], None] = "2551292512f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change api_keys.tenant_id FK from CASCADE to RESTRICT.

    RESTRICT forces the application layer to explicitly delete API keys
    before deleting a tenant, ensuring domain events are emitted for
    SpiceDB cleanup.
    """
    # Drop the existing CASCADE FK constraint
    op.drop_constraint("fk_api_keys_tenant_id", "api_keys", type_="foreignkey")

    # Re-create with RESTRICT instead of CASCADE
    op.create_foreign_key(
        "fk_api_keys_tenant_id",
        "api_keys",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Revert api_keys.tenant_id FK to CASCADE for rollback."""
    op.drop_constraint("fk_api_keys_tenant_id", "api_keys", type_="foreignkey")

    op.create_foreign_key(
        "fk_api_keys_tenant_id",
        "api_keys",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
