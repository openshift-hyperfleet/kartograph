"""SQLAlchemy ORM model for the users table.

Stores user metadata in PostgreSQL. Users are provisioned from SSO
and this table only stores minimal metadata for lookup and reference.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    """ORM model for users table (metadata only).

    Stores user metadata in PostgreSQL. Users are provisioned from SSO
    and this table only stores minimal metadata for lookup and reference.

    Note: id is VARCHAR(255) to accommodate external SSO IDs (UUIDs, Auth0, etc.)
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<UserModel(id={self.id}, username={self.username})>"
