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


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create an engine for one file-backed SQLite database."""

    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite+pysqlite:///{database_path}")


def create_schema(engine: Engine) -> None:
    """Create the current metadata schema for a new MVP database."""

    metadata.create_all(engine)
