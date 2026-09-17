"""Preserve immutable review requests and current canonical pointers."""

import sqlalchemy as sa
from alembic import op

revision = "0004_review_heads"
down_revision = "0003_fact_candidates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_requests",
        sa.Column(
            "decision_id",
            sa.String(36),
            sa.ForeignKey("review_decisions.decision_id"),
            primary_key=True,
        ),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_table(
        "canonical_heads",
        sa.Column("registry", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(), primary_key=True),
        sa.Column("field_name", sa.String(), primary_key=True),
        sa.Column(
            "fact_id",
            sa.String(36),
            sa.ForeignKey("canonical_facts.fact_id"),
            nullable=False,
            unique=True,
        ),
    )


def downgrade():
    op.drop_table("canonical_heads")
    op.drop_table("review_requests")
