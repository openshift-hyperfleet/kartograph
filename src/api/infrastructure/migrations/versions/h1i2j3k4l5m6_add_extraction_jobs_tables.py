"""Add extraction job config and materialized extraction jobs tables.

Revision ID: h1i2j3k4l5m6
Revises: g9h0i1j2k3l4
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, Sequence[str], None] = "g9h0i1j2k3l4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_graphs",
        sa.Column("extraction_job_config", JSONB(), nullable=True),
    )

    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("knowledge_graph_id", sa.String(length=26), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("job_set_name", sa.String(length=128), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_instances", JSONB(), nullable=False, server_default="[]"),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("entities_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entities_modified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationships_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "knowledge_graph_id",
            "job_id",
            name="uq_extraction_jobs_kg_job_id",
        ),
    )
    op.create_index("idx_extraction_jobs_kg_id", "extraction_jobs", ["knowledge_graph_id"])
    op.create_index("idx_extraction_jobs_status", "extraction_jobs", ["status"])

    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("knowledge_graph_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pause_requested", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orchestrator_pid", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "knowledge_graph_id",
            name="uq_extraction_runs_kg_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("extraction_runs")
    op.drop_index("idx_extraction_jobs_status", table_name="extraction_jobs")
    op.drop_index("idx_extraction_jobs_kg_id", table_name="extraction_jobs")
    op.drop_table("extraction_jobs")
    op.drop_column("knowledge_graphs", "extraction_job_config")
