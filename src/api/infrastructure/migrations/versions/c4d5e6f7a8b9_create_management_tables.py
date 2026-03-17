"""create management tables

Create knowledge_graphs, data_sources, and data_source_sync_runs tables
for the Management bounded context persistence layer.

Revision ID: c4d5e6f7a8b9
Revises: 0c6b5d01f040
Create Date: 2026-03-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "0c6b5d01f040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create management tables: knowledge_graphs, data_sources, data_source_sync_runs.

    Key design decisions:
    - No FK on tenant_id or workspace_id (cross-context boundary; integrity
      guaranteed by application logic and SpiceDB).
    - knowledge_graph_id FK uses RESTRICT to prevent orphaning data sources.
    - data_source_id FK uses CASCADE so sync runs are cleaned up with their source.
    - CHECK constraint on sync run status enforces valid state values.
    """
    # 1. knowledge_graphs
    op.create_table(
        "knowledge_graphs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_knowledge_graphs_tenant_name"
        ),
    )

    op.create_index("idx_knowledge_graphs_tenant_id", "knowledge_graphs", ["tenant_id"])
    op.create_index(
        "idx_knowledge_graphs_workspace_id", "knowledge_graphs", ["workspace_id"]
    )

    # 2. data_sources
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "knowledge_graph_id",
            sa.String(26),
            sa.ForeignKey("knowledge_graphs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(26), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("adapter_type", sa.String(50), nullable=False),
        sa.Column("connection_config", JSONB, nullable=False),
        sa.Column("credentials_path", sa.String(500), nullable=True),
        sa.Column("schedule_type", sa.String(50), nullable=False),
        sa.Column("schedule_value", sa.String(255), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "knowledge_graph_id", "name", name="uq_data_sources_kg_name"
        ),
    )

    op.create_index(
        "idx_data_sources_knowledge_graph_id", "data_sources", ["knowledge_graph_id"]
    )
    op.create_index("idx_data_sources_tenant_id", "data_sources", ["tenant_id"])

    # 3. data_source_sync_runs
    op.create_table(
        "data_source_sync_runs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "data_source_id",
            sa.String(26),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_sync_runs_status",
        ),
    )

    op.create_index(
        "idx_sync_runs_data_source_id", "data_source_sync_runs", ["data_source_id"]
    )
    op.create_index(
        "idx_sync_runs_data_source_status",
        "data_source_sync_runs",
        ["data_source_id", "status"],
    )


def downgrade() -> None:
    """Drop management tables in reverse order."""
    # 3. data_source_sync_runs
    op.drop_index(
        "idx_sync_runs_data_source_status", table_name="data_source_sync_runs"
    )
    op.drop_index("idx_sync_runs_data_source_id", table_name="data_source_sync_runs")
    op.drop_table("data_source_sync_runs")

    # 2. data_sources
    op.drop_index("idx_data_sources_tenant_id", table_name="data_sources")
    op.drop_index("idx_data_sources_knowledge_graph_id", table_name="data_sources")
    op.drop_table("data_sources")

    # 1. knowledge_graphs
    op.drop_index("idx_knowledge_graphs_workspace_id", table_name="knowledge_graphs")
    op.drop_index("idx_knowledge_graphs_tenant_id", table_name="knowledge_graphs")
    op.drop_table("knowledge_graphs")
