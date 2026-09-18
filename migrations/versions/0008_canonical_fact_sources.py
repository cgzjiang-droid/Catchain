"""Persist the document-version provenance of each canonical fact."""

import sqlalchemy as sa
from alembic import op

revision = "0008_canonical_fact_sources"
down_revision = "0007_processing_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_fact_sources",
        sa.Column("fact_id", sa.String(36), sa.ForeignKey("canonical_facts.fact_id"), primary_key=True),
        sa.Column(
            "document_version_id",
            sa.String(36),
            sa.ForeignKey("document_versions.document_version_id"),
            nullable=False,
        ),
        sa.Column(
            "parsed_document_id",
            sa.String(36),
            sa.ForeignKey("parsed_documents.parsed_document_id"),
            nullable=False,
        ),
        sa.Column(
            "validation_run_id",
            sa.String(36),
            sa.ForeignKey("processing_runs.pipeline_run_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("canonical_fact_sources")

