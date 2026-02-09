"""create workspaces table

Revision ID: 205809969bf4
Revises: 36612dcd7676
Create Date: 2026-02-06 15:35:32.767286

Creates the workspaces table for organizing knowledge graphs within tenants.
Uses RESTRICT FK constraints to force application-level cascading and ensure
domain events are emitted for SpiceDB cleanup.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "205809969bf4"
down_revision: Union[str, Sequence[str], None] = "36612dcd7676"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workspaces table with RESTRICT FK constraints.

    Key constraints:
    - tenant_id FK with RESTRICT (forces explicit workspace deletion before tenant)
    - parent_workspace_id self-FK with RESTRICT (prevents deleting parent with children)
    - Partial unique index ensures only one root workspace per tenant
    """
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(26),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "parent_workspace_id",
            sa.String(26),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_root", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    # Index on tenant_id for listing workspaces by tenant
    op.create_index("idx_workspaces_tenant_id", "workspaces", ["tenant_id"])

    # Index on parent_workspace_id for hierarchy queries
    op.create_index("idx_workspaces_parent", "workspaces", ["parent_workspace_id"])

    # Composite index for name + tenant lookups
    op.create_index("idx_workspaces_name_tenant", "workspaces", ["name", "tenant_id"])

    # Partial unique index: only one root workspace per tenant
    op.create_index(
        "idx_workspaces_root_unique",
        "workspaces",
        ["tenant_id", "is_root"],
        unique=True,
        postgresql_where=sa.text("is_root = TRUE"),
    )


def downgrade() -> None:
    """Drop workspaces table and all associated indexes."""
    op.drop_index("idx_workspaces_root_unique", table_name="workspaces")
    op.drop_index("idx_workspaces_name_tenant", table_name="workspaces")
    op.drop_index("idx_workspaces_parent", table_name="workspaces")
    op.drop_index("idx_workspaces_tenant_id", table_name="workspaces")
    op.drop_table("workspaces")
