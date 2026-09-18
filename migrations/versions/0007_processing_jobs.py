"""Add durable processing jobs for resumable workers."""

import sqlalchemy as sa
from alembic import op

revision = "0007_processing_jobs"
down_revision = "0006_production_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("input_identity", sa.String(255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.String()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("kind", "input_identity", name="uq_processing_job_identity"),
    )


def downgrade() -> None:
    op.drop_table("processing_jobs")

