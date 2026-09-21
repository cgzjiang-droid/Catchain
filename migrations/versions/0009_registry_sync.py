"""Persist registry sync history and replay-safe checkpoints."""

import sqlalchemy as sa
from alembic import op

revision = "0009_registry_sync"
down_revision = "0008_canonical_fact_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registry_sync_runs",
        sa.Column("sync_run_id", sa.String(36), primary_key=True),
        sa.Column("registry", sa.String(32), nullable=False),
        sa.Column("cursor_before", sa.String()),
        sa.Column("cursor_after", sa.String()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("discovered_projects", sa.Integer(), nullable=False),
        sa.Column("discovered_documents", sa.Integer(), nullable=False),
        sa.Column("failures_json", sa.Text(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String(), nullable=False),
    )
    op.create_table(
        "registry_sync_checkpoints",
        sa.Column("registry", sa.String(32), primary_key=True),
        sa.Column("cursor", sa.String()),
        sa.Column(
            "last_run_id",
            sa.String(36),
            sa.ForeignKey("registry_sync_runs.sync_run_id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("registry_sync_checkpoints")
    op.drop_table("registry_sync_runs")
