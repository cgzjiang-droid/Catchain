"""Add immutable object-storage receipts for production metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0006_production_storage"
down_revision = "0005_evaluation_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stored_objects",
        sa.Column("object_key", sa.String(512), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stored_objects")

