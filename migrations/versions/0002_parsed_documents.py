"""Create parsed-document and parsed-page tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_parsed_documents"
down_revision: str | None = "0001_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parsed_documents",
        sa.Column("parsed_document_id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(), nullable=False),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("ocr_engine_name", sa.String(), nullable=True),
        sa.Column("ocr_engine_version", sa.String(), nullable=True),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_versions.document_version_id"]
        ),
        sa.PrimaryKeyConstraint("parsed_document_id"),
        sa.UniqueConstraint(
            "document_version_id",
            "configuration_hash",
            name="uq_parsed_document_configuration",
        ),
    )
    op.create_table(
        "parsed_pages",
        sa.Column("parsed_document_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("non_whitespace_count", sa.Integer(), nullable=False),
        sa.Column("alphanumeric_ratio", sa.Float(), nullable=False),
        sa.Column("replacement_character_ratio", sa.Float(), nullable=False),
        sa.Column("used_ocr", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parsed_document_id"],
            ["parsed_documents.parsed_document_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("parsed_document_id", "page_number"),
    )


def downgrade() -> None:
    op.drop_table("parsed_pages")
    op.drop_table("parsed_documents")
