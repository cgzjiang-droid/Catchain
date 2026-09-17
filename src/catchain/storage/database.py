"""SQLite engine and table definitions for CATchain."""

from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

source_documents = Table(
    "source_documents",
    metadata,
    Column("source_document_id", String(36), primary_key=True),
    Column("registry", String(32), nullable=False),
    Column("registry_project_id", String, nullable=False),
    Column("source_url", String, nullable=False),
    Column("document_type", String(64), nullable=False),
    Column("title", String),
    Column("discovered_at", String, nullable=False),
)

document_versions = Table(
    "document_versions",
    metadata,
    Column("document_version_id", String(36), primary_key=True),
    Column(
        "source_document_id",
        String(36),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    ),
    Column("sha256", String(64), nullable=False),
    Column("retrieved_at", String, nullable=False),
    Column("content_type", String, nullable=False),
    Column("file_name", String, nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column("declared_version", String),
    UniqueConstraint("source_document_id", "sha256", name="uq_document_version_content"),
)

parsed_documents = Table(
    "parsed_documents",
    metadata,
    Column("parsed_document_id", String(36), primary_key=True),
    Column(
        "document_version_id",
        String(36),
        ForeignKey("document_versions.document_version_id"),
        nullable=False,
    ),
    Column("configuration_hash", String(64), nullable=False),
    Column("parser_name", String, nullable=False),
    Column("parser_version", String, nullable=False),
    Column("ocr_engine_name", String),
    Column("ocr_engine_version", String),
    Column("warnings_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint(
        "document_version_id",
        "configuration_hash",
        name="uq_parsed_document_configuration",
    ),
)

parsed_pages = Table(
    "parsed_pages",
    metadata,
    Column(
        "parsed_document_id",
        String(36),
        ForeignKey("parsed_documents.parsed_document_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("page_number", Integer, primary_key=True),
    Column("text", Text, nullable=False),
    Column("char_start", Integer, nullable=False),
    Column("char_end", Integer, nullable=False),
    Column("character_count", Integer, nullable=False),
    Column("non_whitespace_count", Integer, nullable=False),
    Column("alphanumeric_ratio", Float, nullable=False),
    Column("replacement_character_ratio", Float, nullable=False),
    Column("used_ocr", Boolean, nullable=False),
)


processing_runs = Table(
    "processing_runs",
    metadata,
    Column("pipeline_run_id", String(36), primary_key=True),
    Column("payload_json", Text, nullable=False),
)
validation_reports = Table(
    "validation_reports",
    metadata,
    Column(
        "pipeline_run_id",
        String(36),
        ForeignKey("processing_runs.pipeline_run_id"),
        primary_key=True,
    ),
    Column(
        "extraction_run_id",
        String(36),
        ForeignKey("processing_runs.pipeline_run_id"),
        nullable=False,
    ),
    Column("extraction_json", Text, nullable=False),
    Column(
        "parsed_document_id",
        String(36),
        ForeignKey("parsed_documents.parsed_document_id"),
        nullable=False,
    ),
    Column("registry", String(32), nullable=False),
    Column("project_id", String, nullable=False),
    Column("payload_json", Text, nullable=False),
)
fact_candidates = Table(
    "fact_candidates",
    metadata,
    Column("candidate_id", String(36), primary_key=True),
    Column(
        "validation_run_id",
        String(36),
        ForeignKey("validation_reports.pipeline_run_id"),
        nullable=False,
    ),
    Column("observation_index", Integer, nullable=False),
    Column("field_name", String, nullable=False),
    Column("value_json", Text, nullable=False),
    Column("unit", String),
    Column("validation_status", String, nullable=False),
    Column("issues_json", Text, nullable=False),
    UniqueConstraint("validation_run_id", "observation_index", name="uq_candidate_position"),
)
candidate_evidence = Table(
    "candidate_evidence",
    metadata,
    Column(
        "candidate_id", String(36), ForeignKey("fact_candidates.candidate_id"), primary_key=True
    ),
    Column("evidence_index", Integer, primary_key=True),
    Column(
        "document_version_id",
        String(36),
        ForeignKey("document_versions.document_version_id"),
        nullable=False,
    ),
    Column("page_number", Integer, nullable=False),
    Column("quote", Text, nullable=False),
    Column("char_start", Integer),
    Column("char_end", Integer),
)
review_decisions = Table(
    "review_decisions",
    metadata,
    Column("decision_id", String(36), primary_key=True),
    Column("candidate_id", String(36), ForeignKey("fact_candidates.candidate_id"), nullable=False),
    Column("reviewer", String, nullable=False),
    Column("reason", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("before_value_json", Text, nullable=False),
    Column("after_value_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
)
canonical_facts = Table(
    "canonical_facts",
    metadata,
    Column("fact_id", String(36), primary_key=True),
    Column(
        "decision_id",
        String(36),
        ForeignKey("review_decisions.decision_id"),
        nullable=False,
        unique=True,
    ),
    Column("registry", String(32), nullable=False),
    Column("project_id", String, nullable=False),
    Column("field_name", String, nullable=False),
    Column("value_json", Text, nullable=False),
    Column("unit", String),
)


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create an engine for one file-backed SQLite database."""

    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def create_schema(engine: Engine) -> None:
    """Create the current metadata schema for a new MVP database."""

    metadata.create_all(engine)
