"""SQLAlchemy ORM model for the api_keys table.

Stores API key metadata in PostgreSQL. The key_hash is the only
sensitive data stored - the plaintext secret is never persisted.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class APIKeyModel(Base, TimestampMixin):
    """ORM model for api_keys table.

    Stores API key metadata in PostgreSQL. The key_hash is the only
    sensitive data stored - the plaintext secret is never persisted.

    Notes:
    - created_by_user_id is VARCHAR(255) to match users.id (external SSO IDs)
      This is for audit trail only - authorization is handled by SpiceDB.
    - tenant_id is VARCHAR(26) for ULID format
    - key_hash is unique for authentication lookup
    - prefix allows key identification without exposing the full key
    - Per-user key names are unique within a tenant

    Foreign Key Constraint:
    - tenant_id references tenants.id with RESTRICT delete
      Application must delete API keys before tenant deletion
    - API key deletion must be handled in service layer to emit events
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "created_by_user_id",
            "name",
            name="uq_api_keys_tenant_user_name",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<APIKeyModel(id={self.id}, created_by_user_id={self.created_by_user_id}, "
            f"name={self.name}, prefix={self.prefix})>"
        )
