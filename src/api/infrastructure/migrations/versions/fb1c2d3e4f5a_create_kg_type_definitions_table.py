"""Create knowledge_graph_type_definitions table for canonical schema storage.

Revision ID: fb1c2d3e4f5a
Revises: fa0b1c2d3e4f
Create Date: 2026-05-22 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "fb1c2d3e4f5a"
down_revision = "fa0b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create table for graph-native canonical type definitions."""
    op.create_table(
        "knowledge_graph_type_definitions",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("knowledge_graph_id", sa.String(length=26), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column(
            "description", sa.String(length=2048), nullable=False, server_default=""
        ),
        sa.Column(
            "required_properties",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "optional_properties",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_graph_id",
            "entity_type",
            "label",
            name="uq_kg_type_definitions_kg_entity_label",
        ),
    )
    op.create_index(
        "ix_knowledge_graph_type_definitions_knowledge_graph_id",
        "knowledge_graph_type_definitions",
        ["knowledge_graph_id"],
    )


def downgrade() -> None:
    """Drop canonical type definition table."""
    op.drop_index(
        "ix_knowledge_graph_type_definitions_knowledge_graph_id",
        table_name="knowledge_graph_type_definitions",
    )
    op.drop_table("knowledge_graph_type_definitions")
