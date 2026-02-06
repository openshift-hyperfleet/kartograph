"""fix groups tenant cascade constraint

Revision ID: 36612dcd7676
Revises: 193b7c6ad230
Create Date: 2026-02-06 15:34:59.572180

Changes CASCADE to RESTRICT on groups.tenant_id FK to force application-level
cascading. This ensures GroupDeleted domain events are emitted when groups are
removed, preventing orphaned SpiceDB relationships.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "36612dcd7676"
down_revision: Union[str, Sequence[str], None] = "193b7c6ad230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change groups.tenant_id FK from CASCADE to RESTRICT.

    RESTRICT forces the application layer to explicitly delete groups
    before deleting a tenant, ensuring domain events are emitted for
    SpiceDB cleanup.
    """
    # Drop the existing CASCADE FK constraint
    op.drop_constraint("fk_groups_tenant_id", "groups", type_="foreignkey")

    # Re-create with RESTRICT instead of CASCADE
    op.create_foreign_key(
        "fk_groups_tenant_id",
        "groups",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Revert groups.tenant_id FK to CASCADE for rollback."""
    op.drop_constraint("fk_groups_tenant_id", "groups", type_="foreignkey")

    op.create_foreign_key(
        "fk_groups_tenant_id",
        "groups",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
