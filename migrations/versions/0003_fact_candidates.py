"""Create candidate, evidence, validation and future review/fact tables (SQLite)."""

from alembic import op

revision = "0003_fact_candidates"
down_revision = "0002_parsed_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE processing_runs (
	pipeline_run_id VARCHAR(36) NOT NULL,
	payload_json TEXT NOT NULL,
	PRIMARY KEY (pipeline_run_id)
)

""")
    op.execute("""
CREATE TABLE validation_reports (
	pipeline_run_id VARCHAR(36) NOT NULL,
	extraction_run_id VARCHAR(36) NOT NULL,
	extraction_json TEXT NOT NULL,
	parsed_document_id VARCHAR(36) NOT NULL,
	registry VARCHAR(32) NOT NULL,
	project_id VARCHAR NOT NULL,
	payload_json TEXT NOT NULL,
	PRIMARY KEY (pipeline_run_id),
	FOREIGN KEY(pipeline_run_id) REFERENCES processing_runs (pipeline_run_id),
	FOREIGN KEY(extraction_run_id) REFERENCES processing_runs (pipeline_run_id),
	FOREIGN KEY(parsed_document_id) REFERENCES parsed_documents (parsed_document_id)
)

""")
    op.execute("""
CREATE TABLE fact_candidates (
	candidate_id VARCHAR(36) NOT NULL,
	validation_run_id VARCHAR(36) NOT NULL,
	observation_index INTEGER NOT NULL,
	field_name VARCHAR NOT NULL,
	value_json TEXT NOT NULL,
	unit VARCHAR,
	validation_status VARCHAR NOT NULL,
	issues_json TEXT NOT NULL,
	PRIMARY KEY (candidate_id),
	CONSTRAINT uq_candidate_position UNIQUE (validation_run_id, observation_index),
	FOREIGN KEY(validation_run_id) REFERENCES validation_reports (pipeline_run_id)
)

""")
    op.execute("""
CREATE TABLE candidate_evidence (
	candidate_id VARCHAR(36) NOT NULL,
	evidence_index INTEGER NOT NULL,
	document_version_id VARCHAR(36) NOT NULL,
	page_number INTEGER NOT NULL,
	quote TEXT NOT NULL,
	char_start INTEGER,
	char_end INTEGER,
	PRIMARY KEY (candidate_id, evidence_index),
	FOREIGN KEY(candidate_id) REFERENCES fact_candidates (candidate_id),
	FOREIGN KEY(document_version_id) REFERENCES document_versions (document_version_id)
)

""")
    op.execute("""
CREATE TABLE review_decisions (
	decision_id VARCHAR(36) NOT NULL,
	candidate_id VARCHAR(36) NOT NULL,
	reviewer VARCHAR NOT NULL,
	reason TEXT NOT NULL,
	status VARCHAR NOT NULL,
	before_value_json TEXT NOT NULL,
	after_value_json TEXT NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (decision_id),
	FOREIGN KEY(candidate_id) REFERENCES fact_candidates (candidate_id)
)

""")
    op.execute("""
CREATE TABLE canonical_facts (
	fact_id VARCHAR(36) NOT NULL,
	decision_id VARCHAR(36) NOT NULL,
	registry VARCHAR(32) NOT NULL,
	project_id VARCHAR NOT NULL,
	field_name VARCHAR NOT NULL,
	value_json TEXT NOT NULL,
	unit VARCHAR,
	PRIMARY KEY (fact_id),
	UNIQUE (decision_id),
	FOREIGN KEY(decision_id) REFERENCES review_decisions (decision_id)
)

""")


def downgrade() -> None:
    op.drop_table("canonical_facts")
    op.drop_table("review_decisions")
    op.drop_table("candidate_evidence")
    op.drop_table("fact_candidates")
    op.drop_table("validation_reports")
    op.drop_table("processing_runs")
