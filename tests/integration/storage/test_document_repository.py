from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from catchain.domain import DocumentType, DocumentVersion, Registry, SourceDocument
from catchain.storage.database import create_schema, create_sqlite_engine
from catchain.storage.document_repository import (
    DuplicateDocumentVersionError,
    SqlAlchemyDocumentRepository,
)

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")


def build_source() -> SourceDocument:
    return SourceDocument(
        source_document_id=SOURCE_ID,
        registry=Registry.VERRA,
        registry_project_id="VCS-1234",
        source_url="https://registry.example/projects/1234/pdd.pdf",
        document_type=DocumentType.PROJECT_DESCRIPTION,
        title="Project design document",
        discovered_at=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
    )


def build_version(*, sha256: str, day: int) -> DocumentVersion:
    return DocumentVersion(
        document_version_id=UUID(f"22222222-2222-2222-2222-{day:012d}"),
        source_document_id=SOURCE_ID,
        sha256=sha256,
        retrieved_at=datetime(2026, 9, day, 9, 0, tzinfo=UTC),
        content_type="application/pdf",
        file_name=f"pdd-v{day}.pdf",
        byte_size=day,
        declared_version=f"v{day}",
    )


def make_repository(tmp_path: Path) -> SqlAlchemyDocumentRepository:
    engine = create_sqlite_engine(tmp_path / "catchain.sqlite")
    create_schema(engine)
    return SqlAlchemyDocumentRepository(engine)


def test_repository_round_trips_source_document(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    source = build_source()

    repository.add_source(source)

    assert repository.get_source(SOURCE_ID) == source


def test_repository_lists_document_versions_in_retrieval_order(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.add_source(build_source())
    later = build_version(sha256="b" * 64, day=14)
    earlier = build_version(sha256="a" * 64, day=13)

    repository.add_version(later)
    repository.add_version(earlier)

    assert repository.list_versions(SOURCE_ID) == [earlier, later]
    assert repository.find_version_by_hash(SOURCE_ID, "b" * 64) == later


def test_repository_rejects_duplicate_content_for_one_source(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.add_source(build_source())
    version = build_version(sha256="a" * 64, day=13)
    repository.add_version(version)
    duplicate = version.model_copy(
        update={"document_version_id": UUID("33333333-3333-3333-3333-333333333333")}
    )

    with pytest.raises(DuplicateDocumentVersionError):
        repository.add_version(duplicate)
