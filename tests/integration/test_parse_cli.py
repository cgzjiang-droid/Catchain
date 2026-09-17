import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pymupdf
from sqlalchemy import func, select
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain import DocumentType, DocumentVersion, Registry, SourceDocument
from catchain.ingestion import RawBlobStore
from catchain.storage.database import (
    create_schema,
    create_sqlite_engine,
    parsed_documents,
)
from catchain.storage.document_repository import SqlAlchemyDocumentRepository

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")


def prepare_raw_document(tmp_path: Path) -> tuple[Path, Path]:
    pdf_path = tmp_path / "project.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Traceable native project text")
    document.save(pdf_path)
    document.close()

    database_path = tmp_path / "catchain.sqlite"
    raw_root = tmp_path / "raw"
    stored = RawBlobStore(raw_root).store_file(pdf_path)
    engine = create_sqlite_engine(database_path)
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
            sha256=stored.sha256,
            retrieved_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
            content_type="application/pdf",
            file_name=pdf_path.name,
            byte_size=stored.byte_size,
        )
    )
    return database_path, raw_root


def test_parse_raw_stores_then_reuses_structured_result(tmp_path: Path) -> None:
    database_path, raw_root = prepare_raw_document(tmp_path)
    arguments = [
        "parse",
        "raw",
        str(VERSION_ID),
        "--database",
        str(database_path),
        "--raw-root",
        str(raw_root),
        "--min-non-whitespace",
        "0",
    ]
    runner = CliRunner()

    first = runner.invoke(app, arguments)
    second = runner.invoke(app, arguments)

    assert first.exit_code == 0
    first_output = json.loads(first.stdout)
    assert first_output["status"] == "stored"
    assert first_output["page_count"] == 1
    assert first_output["ocr_page_count"] == 0
    assert second.exit_code == 0
    second_output = json.loads(second.stdout)
    assert second_output["status"] == "reused"
    assert second_output["parsed_document_id"] == first_output["parsed_document_id"]

    engine = create_sqlite_engine(database_path)
    with engine.connect() as connection:
        parsed_count = connection.scalar(
            select(func.count()).select_from(parsed_documents)
        )
    assert parsed_count == 1


def test_parse_raw_reports_unknown_document_version_as_json(tmp_path: Path) -> None:
    database_path = tmp_path / "catchain.sqlite"
    raw_root = tmp_path / "raw"

    result = CliRunner().invoke(
        app,
        [
            "parse",
            "raw",
            str(VERSION_ID),
            "--database",
            str(database_path),
            "--raw-root",
            str(raw_root),
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "status": "failed",
        "error_code": "DOCUMENT_VERSION_NOT_FOUND",
        "message": f"document version not found: {VERSION_ID}",
    }
