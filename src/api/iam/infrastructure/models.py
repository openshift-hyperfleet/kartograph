"""SQLAlchemy ORM models for IAM bounded context.

These models map to database tables and are used by repository implementations.
They store only metadata - authorization data (membership, roles) is stored in SpiceDB.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class GroupModel(Base, TimestampMixin):
    """ORM model for groups table (metadata only).

    Stores group metadata in PostgreSQL. Membership relationships are
    managed through SpiceDB, not as database columns.

    Note: Group names are NOT globally unique - per-tenant uniqueness
    is enforced at the application level.
    """

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<GroupModel(id={self.id}, tenant_id={self.tenant_id}, name={self.name})>"
        )


class UserModel(Base, TimestampMixin):
    """ORM model for users table (metadata only).

    Stores user metadata in PostgreSQL. Users are provisioned from SSO
    and this table only stores minimal metadata for lookup and reference.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<UserModel(id={self.id}, username={self.username})>"


class TenantModel(Base, TimestampMixin):
    """ORM model for tenants table.

    Stores tenant metadata in PostgreSQL. Tenants represent organizations
    and are the top-level isolation boundary in the system.

    Note: Tenant names are globally unique across the entire system.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<TenantModel(id={self.id}, name={self.name})>"
