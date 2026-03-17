"""SQLAlchemy ORM model for the data_sources table.

Stores data source configuration in PostgreSQL. Data sources define
how data is ingested into a knowledge graph from external systems.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class DataSourceModel(Base, TimestampMixin):
    """ORM model for data_sources table.

    Stores data source configuration in PostgreSQL. Each data source
    belongs to exactly one knowledge graph and one tenant.

    Foreign Key Constraints:
    - knowledge_graph_id references knowledge_graphs.id with RESTRICT delete
      Application must delete data sources before knowledge graph deletion
    """

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    knowledge_graph_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("knowledge_graphs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    credentials_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("knowledge_graph_id", "name", name="uq_data_sources_kg_name"),
        Index("idx_data_sources_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<DataSourceModel(id={self.id}, knowledge_graph_id={self.knowledge_graph_id}, "
            f"name={self.name}, adapter_type={self.adapter_type})>"
        )
