"""SQLAlchemy ORM models for IAM bounded context.

These models map to database tables and are used by repository implementations.
They store only metadata - authorization data (membership, roles) is stored in SpiceDB.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class GroupModel(Base, TimestampMixin):
    """ORM model for groups table (metadata only).

    Stores group metadata in PostgreSQL. Workspace relationships and
    membership are managed through SpiceDB, not as database columns.
    """

    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<GroupModel(id={self.id}, name={self.name})>"


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
