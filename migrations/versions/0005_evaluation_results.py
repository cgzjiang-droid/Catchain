"""Persist evidence-grounded evaluation results separately from JSON artifacts."""

import sqlalchemy as sa
from alembic import op

revision = "0005_evaluation_results"
down_revision = "0004_review_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_results",
        sa.Column("evaluation_result_id", sa.String(36), primary_key=True),
        sa.Column(
            "pipeline_run_id",
            sa.String(36),
            sa.ForeignKey("processing_runs.pipeline_run_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("registry", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("rubric_version", sa.String(), nullable=False),
        sa.Column("rubric_sha256", sa.String(64), nullable=False),
        sa.Column("score_status", sa.String(), nullable=False),
        sa.Column("total_score", sa.Float()),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "pipeline_run_id", "rubric_sha256", name="uq_evaluation_result_run_rubric"
        ),
    )


def downgrade() -> None:
    op.drop_table("evaluation_results")
