"""create encrypted_credentials table

Adds the encrypted_credentials table for Fernet-encrypted credential
storage in the Management bounded context.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create encrypted_credentials table with composite PK (path, tenant_id)."""
    op.create_table(
        "encrypted_credentials",
        sa.Column("path", sa.String(500), primary_key=True),
        sa.Column("tenant_id", sa.String(26), primary_key=True),
        sa.Column("encrypted_value", sa.LargeBinary, nullable=False),
        sa.Column("key_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Drop encrypted_credentials table."""
    op.drop_table("encrypted_credentials")
