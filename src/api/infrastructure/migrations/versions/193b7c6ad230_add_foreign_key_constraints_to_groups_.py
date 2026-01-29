"""add foreign key constraints to groups and api_keys

Revision ID: 193b7c6ad230
Revises: 8a9b0c1d2e3f
Create Date: 2026-01-29 15:12:22.250189

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "193b7c6ad230"
down_revision: Union[str, Sequence[str], None] = "8a9b0c1d2e3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CASCADE foreign key constraints for tenant relationships.

    This ensures referential integrity and enables cascade deletion:
    - When a tenant is deleted, all groups are cascade deleted
    - When a tenant is deleted, all API keys are cascade deleted

    Note: Service layer must explicitly delete child aggregates before
    tenant deletion to ensure proper domain events are emitted for
    SpiceDB cleanup.
    """
    # Add FK constraint to groups.tenant_id
    op.create_foreign_key(
        "fk_groups_tenant_id",
        "groups",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add FK constraint to api_keys.tenant_id
    op.create_foreign_key(
        "fk_api_keys_tenant_id",
        "api_keys",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove CASCADE foreign key constraints."""
    # Drop FK constraint from api_keys.tenant_id
    op.drop_constraint("fk_api_keys_tenant_id", "api_keys", type_="foreignkey")

    # Drop FK constraint from groups.tenant_id
    op.drop_constraint("fk_groups_tenant_id", "groups", type_="foreignkey")
