"""SQLAlchemy ORM model for the knowledge_graphs table.

Stores knowledge graph metadata in PostgreSQL. Knowledge graphs are
containers for interconnected data within a workspace.
"""

import sqlalchemy as sa
from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class KnowledgeGraphModel(Base, TimestampMixin):
    """ORM model for knowledge_graphs table.

    Stores knowledge graph metadata in PostgreSQL. Each knowledge graph
    belongs to exactly one workspace and one tenant.

    Cross-Context References:
    - tenant_id references tenants in the IAM context (no FK — cross-boundary)
    - workspace_id references workspaces in the IAM context (no FK — cross-boundary)
    """

    __tablename__ = "knowledge_graphs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_knowledge_graphs_tenant_name"),
        Index("idx_knowledge_graphs_tenant_id", "tenant_id"),
        Index("idx_knowledge_graphs_workspace_id", "workspace_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<KnowledgeGraphModel(id={self.id}, tenant_id={self.tenant_id}, "
            f"name={self.name})>"
        )
