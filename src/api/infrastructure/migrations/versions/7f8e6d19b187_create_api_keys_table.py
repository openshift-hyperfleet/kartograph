"""create api_keys table

Revision ID: 7f8e6d19b187
Revises: 361d2df03685
Create Date: 2026-01-21

Creates the api_keys table for storing API key metadata.
API keys provide programmatic access as an alternative to OIDC tokens.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f8e6d19b187"
down_revision: Union[str, Sequence[str], None] = "361d2df03685"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_keys table with all columns and indexes."""
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(26), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("prefix", sa.String(12), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "name", name="uq_api_keys_tenant_user_name"
        ),
    )

    # Create composite index for user listing queries
    op.create_index(
        "ix_api_keys_tenant_id_user_id",
        "api_keys",
        ["tenant_id", "user_id"],
    )


def downgrade() -> None:
    """Drop api_keys table."""
    op.drop_index("ix_api_keys_tenant_id_user_id", table_name="api_keys")
    op.drop_table("api_keys")
