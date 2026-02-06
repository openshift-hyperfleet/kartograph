"""SQLAlchemy ORM model for the tenants table.

Stores tenant metadata in PostgreSQL. Tenants represent organizations
and are the top-level isolation boundary in the system.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.models import Base, TimestampMixin


class TenantModel(Base, TimestampMixin):
    """ORM model for tenants table.

    Stores tenant metadata in PostgreSQL. Tenants represent organizations
    and are the top-level isolation boundary in the system.

    Note: Tenant names are globally unique across the entire system.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Relationships
    workspaces = relationship("WorkspaceModel", back_populates="tenant")

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<TenantModel(id={self.id}, name={self.name})>"
