from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from catchain.domain import (
    DocumentType,
    DocumentVersion,
    ParsedDocument,
    ParsedPage,
    Registry,
    SourceDocument,
    TextQuality,
)
from catchain.storage.database import create_schema, create_sqlite_engine
from catchain.storage.document_repository import (
    DuplicateParsedDocumentError,
    SqlAlchemyDocumentRepository,
)

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")
CONFIGURATION_HASH = "c" * 64


def make_repository(tmp_path: Path) -> SqlAlchemyDocumentRepository:
    engine = create_sqlite_engine(tmp_path / "catchain.sqlite")
    create_schema(engine)
    repository = SqlAlchemyDocumentRepository(engine)
    repository.add_source(
        SourceDocument(
            source_document_id=SOURCE_ID,
            registry=Registry.VERRA,
            registry_project_id="VCS-1234",
            source_url="https://registry.example/projects/1234/pdd.pdf",
            document_type=DocumentType.PROJECT_DESCRIPTION,
            discovered_at=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
        )
    )
    repository.add_version(
        DocumentVersion(
            document_version_id=VERSION_ID,
            source_document_id=SOURCE_ID,
            sha256="a" * 64,
            retrieved_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
            content_type="application/pdf",
            file_name="pdd.pdf",
            byte_size=100,
        )
    )
    return repository


def parsed_page(page_number: int, text: str, *, used_ocr: bool) -> ParsedPage:
    non_whitespace = sum(not character.isspace() for character in text)
    return ParsedPage(
        page_number=page_number,
        text=text,
        char_start=0,
        char_end=len(text),
        quality=TextQuality(
            character_count=len(text),
            non_whitespace_count=non_whitespace,
            alphanumeric_ratio=1.0,
            replacement_character_ratio=0.0,
        ),
        used_ocr=used_ocr,
    )


def build_parsed_document() -> ParsedDocument:
    return ParsedDocument(
        parsed_document_id=UUID("33333333-3333-3333-3333-333333333333"),
        document_version_id=VERSION_ID,
        parser_name="PyMuPDF",
        parser_version="1.26.0",
        ocr_engine_name="Fake OCR",
        ocr_engine_version="test-1",
        pages=(
            parsed_page(1, "native text", used_ocr=False),
            parsed_page(2, "OCR text", used_ocr=True),
        ),
        warnings=("page 3: blank page skipped OCR",),
        created_at=datetime(2026, 9, 14, 10, 0, tzinfo=UTC),
    )


def test_repository_round_trips_parsed_document_by_configuration(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    parsed = build_parsed_document()

    repository.add_parsed(parsed, configuration_hash=CONFIGURATION_HASH)

    assert repository.find_parsed(VERSION_ID, CONFIGURATION_HASH) == parsed


def test_repository_rejects_duplicate_parse_configuration(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    parsed = build_parsed_document()
    repository.add_parsed(parsed, configuration_hash=CONFIGURATION_HASH)
    duplicate = parsed.model_copy(
        update={
            "parsed_document_id": UUID("44444444-4444-4444-4444-444444444444")
        }
    )

    with pytest.raises(DuplicateParsedDocumentError):
        repository.add_parsed(duplicate, configuration_hash=CONFIGURATION_HASH)
