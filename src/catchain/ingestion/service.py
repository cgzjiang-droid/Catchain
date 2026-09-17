"""Application service for importing local source-document files."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from catchain.domain import DocumentVersion, SourceDocument
from catchain.ingestion.raw_store import RawBlobStore


class DocumentRepository(Protocol):
    """Persistence operations required by local ingestion."""

    def add_source(self, source: SourceDocument) -> None: ...

    def get_source(self, source_document_id: UUID) -> SourceDocument | None: ...

    def add_version(self, version: DocumentVersion) -> None: ...

    def find_version_by_hash(
        self, source_document_id: UUID, sha256: str
    ) -> DocumentVersion | None: ...


class SourceDocumentConflictError(ValueError):
    """An existing source identity has different traceability metadata."""


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Result of importing local bytes and version metadata."""

    document_version: DocumentVersion
    raw_path: Path
    duplicate: bool


def ingest_local_document(
    *,
    source_document: SourceDocument,
    local_path: Path,
    content_type: str,
    retrieved_at: datetime,
    declared_version: str | None,
    raw_store: RawBlobStore,
    repository: DocumentRepository,
) -> IngestionResult:
    """Import one local file without losing or duplicating content versions."""

    existing_source = repository.get_source(source_document.source_document_id)
    if existing_source is None:
        repository.add_source(source_document)
    elif existing_source != source_document:
        raise SourceDocumentConflictError(
            f"source metadata conflicts for {source_document.source_document_id}"
        )

    stored_blob = raw_store.store_file(local_path)
    existing_version = repository.find_version_by_hash(
        source_document.source_document_id, stored_blob.sha256
    )
    if existing_version is not None:
        return IngestionResult(
            document_version=existing_version,
            raw_path=stored_blob.path,
            duplicate=True,
        )

    version = DocumentVersion(
        source_document_id=source_document.source_document_id,
        sha256=stored_blob.sha256,
        retrieved_at=retrieved_at,
        content_type=content_type,
        file_name=Path(local_path).name,
        byte_size=stored_blob.byte_size,
        declared_version=declared_version,
    )
    repository.add_version(version)
    return IngestionResult(
        document_version=version,
        raw_path=stored_blob.path,
        duplicate=False,
    )
