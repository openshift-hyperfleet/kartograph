"""SQLAlchemy ORM model for the workspaces table.

Stores workspace metadata in PostgreSQL. Workspaces organize knowledge
graphs within a tenant.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.models import Base, TimestampMixin


class WorkspaceModel(Base, TimestampMixin):
    """ORM model for workspaces table.

    Stores workspace metadata in PostgreSQL. Workspaces organize knowledge
    graphs within a tenant. Each tenant has exactly one root workspace
    (auto-created on tenant creation) and can have multiple child workspaces.

    Foreign Key Constraints:
    - tenant_id references tenants.id with RESTRICT delete
      Application must delete workspaces before tenant deletion
    - parent_workspace_id references workspaces.id with RESTRICT delete
      Cannot delete a parent workspace while children exist

    Partial Unique Index:
    - Only one root workspace (is_root=TRUE) per tenant
    """

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_workspace_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    tenant = relationship("TenantModel", back_populates="workspaces")
    parent_workspace = relationship(
        "WorkspaceModel",
        remote_side="WorkspaceModel.id",
        back_populates="child_workspaces",
    )
    child_workspaces = relationship(
        "WorkspaceModel",
        back_populates="parent_workspace",
    )

    __table_args__ = (
        Index("idx_workspaces_name_tenant", "name", "tenant_id"),
        Index(
            "idx_workspaces_root_unique",
            "tenant_id",
            "is_root",
            unique=True,
            postgresql_where=(is_root == True),  # noqa: E712
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<WorkspaceModel(id={self.id}, tenant_id={self.tenant_id}, "
            f"name={self.name}, is_root={self.is_root})>"
        )
