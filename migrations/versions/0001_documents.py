"""Create source-document and document-version tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_documents"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("registry", sa.String(length=32), nullable=False),
        sa.Column("registry_project_id", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("discovered_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("source_document_id"),
    )
    op.create_table(
        "document_versions",
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("declared_version", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["source_documents.source_document_id"]
        ),
        sa.PrimaryKeyConstraint("document_version_id"),
        sa.UniqueConstraint(
            "source_document_id", "sha256", name="uq_document_version_content"
        ),
    )


def downgrade() -> None:
    op.drop_table("document_versions")
    op.drop_table("source_documents")
