from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from catchain.domain import DocumentType, Registry, SourceDocument
from catchain.ingestion.raw_store import RawBlobStore
from catchain.ingestion.service import SourceDocumentConflictError, ingest_local_document
from catchain.storage.database import create_schema, create_sqlite_engine
from catchain.storage.document_repository import SqlAlchemyDocumentRepository


def test_local_ingestion_reuses_content_and_preserves_changed_versions(tmp_path: Path) -> None:
    source_document = SourceDocument(
        source_document_id=UUID("11111111-1111-1111-1111-111111111111"),
        registry=Registry.VERRA,
        registry_project_id="VCS-1234",
        source_url="https://registry.example/projects/1234/pdd.pdf",
        document_type=DocumentType.PROJECT_DESCRIPTION,
        title="Project design document",
        discovered_at=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
    )
    engine = create_sqlite_engine(tmp_path / "catchain.sqlite")
    create_schema(engine)
    repository = SqlAlchemyDocumentRepository(engine)
    raw_store = RawBlobStore(tmp_path / "raw")
    local_file = tmp_path / "project.pdf"
    local_file.write_bytes(b"first document version")

    first = ingest_local_document(
        source_document=source_document,
        local_path=local_file,
        content_type="application/pdf",
        retrieved_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
        declared_version="v1",
        raw_store=raw_store,
        repository=repository,
    )
    repeated = ingest_local_document(
        source_document=source_document,
        local_path=local_file,
        content_type="application/pdf",
        retrieved_at=datetime(2026, 9, 14, 10, 0, tzinfo=UTC),
        declared_version="v1-copy",
        raw_store=raw_store,
        repository=repository,
    )

    local_file.write_bytes(b"corrected second document version")
    changed = ingest_local_document(
        source_document=source_document,
        local_path=local_file,
        content_type="application/pdf",
        retrieved_at=datetime(2026, 9, 14, 11, 0, tzinfo=UTC),
        declared_version="v2",
        raw_store=raw_store,
        repository=repository,
    )

    versions = repository.list_versions(source_document.source_document_id)
    assert repeated.duplicate is True
    assert repeated.document_version == first.document_version
    assert changed.duplicate is False
    assert versions == [first.document_version, changed.document_version]
    assert first.raw_path.read_bytes() == b"first document version"
    assert changed.raw_path.read_bytes() == b"corrected second document version"


def test_local_ingestion_rejects_conflicting_source_metadata(tmp_path: Path) -> None:
    original = SourceDocument(
        source_document_id=UUID("11111111-1111-1111-1111-111111111111"),
        registry=Registry.VERRA,
        registry_project_id="VCS-1234",
        source_url="https://registry.example/projects/1234/pdd.pdf",
        document_type=DocumentType.PROJECT_DESCRIPTION,
        title="Original title",
        discovered_at=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
    )
    conflicting = original.model_copy(update={"title": "Conflicting title"})
    engine = create_sqlite_engine(tmp_path / "catchain.sqlite")
    create_schema(engine)
    repository = SqlAlchemyDocumentRepository(engine)
    repository.add_source(original)
    local_file = tmp_path / "project.pdf"
    local_file.write_bytes(b"document bytes")

    with pytest.raises(SourceDocumentConflictError):
        ingest_local_document(
            source_document=conflicting,
            local_path=local_file,
            content_type="application/pdf",
            retrieved_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
            declared_version=None,
            raw_store=RawBlobStore(tmp_path / "raw"),
            repository=repository,
        )
