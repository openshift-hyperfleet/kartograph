"""SQLAlchemy model for KG-scoped graph type definitions."""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base


class KnowledgeGraphTypeDefinitionModel(Base):
    """Persisted type definition for a knowledge graph schema layer."""

    __tablename__ = "knowledge_graph_type_definitions"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_graph_id",
            "entity_type",
            "label",
            name="uq_kg_type_definitions_kg_entity_label",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    knowledge_graph_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    required_properties: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    optional_properties: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
