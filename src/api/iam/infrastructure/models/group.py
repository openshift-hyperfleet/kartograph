"""SQLAlchemy ORM model for the groups table.

Stores group metadata in PostgreSQL. Membership relationships are
managed through SpiceDB, not as database columns.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class GroupModel(Base, TimestampMixin):
    """ORM model for groups table (metadata only).

    Stores group metadata in PostgreSQL. Membership relationships are
    managed through SpiceDB, not as database columns.

    Note: Group names are NOT globally unique - per-tenant uniqueness
    is enforced at the application level.

    Foreign Key Constraint:
    - tenant_id references tenants.id with RESTRICT delete
    - Application layer must explicitly delete groups before tenant deletion
    - This ensures GroupDeleted domain events are emitted for SpiceDB cleanup
    """

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<GroupModel(id={self.id}, tenant_id={self.tenant_id}, name={self.name})>"
        )
