"""add unique constraint on workspace name per tenant

Revision ID: 2551292512f6
Revises: 205809969bf4
Create Date: 2026-02-09 14:54:04.502798

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2551292512f6"
down_revision: Union[str, Sequence[str], None] = "205809969bf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on (tenant_id, name) for workspaces."""
    op.create_unique_constraint(
        "uq_workspaces_tenant_name",
        "workspaces",
        ["tenant_id", "name"],
    )


def downgrade() -> None:
    """Remove unique constraint."""
    op.drop_constraint("uq_workspaces_tenant_name", "workspaces", type_="unique")
