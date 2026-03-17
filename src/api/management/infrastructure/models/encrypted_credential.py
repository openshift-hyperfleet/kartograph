"""SQLAlchemy ORM model for the encrypted_credentials table.

Stores Fernet-encrypted credentials in PostgreSQL, scoped by path
and tenant_id. Part of the Management bounded context.
"""

from __future__ import annotations

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class EncryptedCredentialModel(Base, TimestampMixin):
    """ORM model for encrypted_credentials table.

    Stores encrypted credential blobs keyed by (path, tenant_id).
    The key_version column tracks which Fernet key was used for
    encryption to support key rotation.
    """

    __tablename__ = "encrypted_credentials"

    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<EncryptedCredentialModel(path={self.path}, "
            f"tenant_id={self.tenant_id}, key_version={self.key_version})>"
        )
