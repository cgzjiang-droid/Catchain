"""SQLAlchemy repository for source, version, and parsed document records."""

import json
from datetime import datetime
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import Select, insert, select
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from catchain.domain import (
    DocumentVersion,
    ParsedDocument,
    ParsedPage,
    Sha256,
    SourceDocument,
    TextQuality,
)
from catchain.storage.database import (
    document_versions,
    parsed_documents,
    parsed_pages,
    source_documents,
)

SHA256_ADAPTER = TypeAdapter(Sha256)


class DuplicateDocumentVersionError(ValueError):
    """The same source document already has this content hash."""


class DuplicateParsedDocumentError(ValueError):
    """This document version was already parsed with this configuration."""


class SqlAlchemyDocumentRepository:
    """Persist and reconstruct validated document-domain models."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def add_source(self, source: SourceDocument) -> None:
        values = source.model_dump(mode="json")
        with self.engine.begin() as connection:
            connection.execute(insert(source_documents).values(**values))

    def get_source(self, source_document_id: UUID) -> SourceDocument | None:
        statement = select(source_documents).where(
            source_documents.c.source_document_id == str(source_document_id)
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return self._source_from_row(row) if row is not None else None

    def add_version(self, version: DocumentVersion) -> None:
        values = version.model_dump(mode="json")
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(document_versions).values(**values))
        except IntegrityError as error:
            raise DuplicateDocumentVersionError(
                f"document content already exists for source {version.source_document_id}"
            ) from error

    def list_versions(self, source_document_id: UUID) -> list[DocumentVersion]:
        statement = (
            select(document_versions)
            .where(document_versions.c.source_document_id == str(source_document_id))
            .order_by(document_versions.c.retrieved_at, document_versions.c.document_version_id)
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._version_from_row(row) for row in rows]

    def get_version(self, document_version_id: UUID) -> DocumentVersion | None:
        statement = select(document_versions).where(
            document_versions.c.document_version_id == str(document_version_id)
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return self._version_from_row(row) if row is not None else None

    def find_version_by_hash(self, source_document_id: UUID, sha256: str) -> DocumentVersion | None:
        statement = select(document_versions).where(
            document_versions.c.source_document_id == str(source_document_id),
            document_versions.c.sha256 == sha256,
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return self._version_from_row(row) if row is not None else None

    def add_parsed(self, parsed: ParsedDocument, *, configuration_hash: str) -> None:
        configuration_hash = SHA256_ADAPTER.validate_python(configuration_hash)
        document_values = parsed.model_dump(mode="json", exclude={"pages", "warnings"})
        document_values["configuration_hash"] = configuration_hash
        document_values["warnings_json"] = json.dumps(list(parsed.warnings), ensure_ascii=False)
        page_values = [
            {
                "parsed_document_id": str(parsed.parsed_document_id),
                "page_number": page.page_number,
                "text": page.text,
                "char_start": page.char_start,
                "char_end": page.char_end,
                "character_count": page.quality.character_count,
                "non_whitespace_count": page.quality.non_whitespace_count,
                "alphanumeric_ratio": page.quality.alphanumeric_ratio,
                "replacement_character_ratio": (page.quality.replacement_character_ratio),
                "used_ocr": page.used_ocr,
            }
            for page in parsed.pages
        ]
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(parsed_documents).values(**document_values))
                connection.execute(insert(parsed_pages), page_values)
        except IntegrityError as error:
            raise DuplicateParsedDocumentError(
                "document version already parsed with this configuration"
            ) from error

    def find_parsed(
        self, document_version_id: UUID, configuration_hash: str
    ) -> ParsedDocument | None:
        configuration_hash = SHA256_ADAPTER.validate_python(configuration_hash)
        statement = select(parsed_documents).where(
            parsed_documents.c.document_version_id == str(document_version_id),
            parsed_documents.c.configuration_hash == configuration_hash,
        )
        return self._read_parsed(statement)

    def get_parsed(self, parsed_document_id: UUID) -> ParsedDocument | None:
        return self._read_parsed(
            select(parsed_documents).where(
                parsed_documents.c.parsed_document_id == str(parsed_document_id)
            )
        )

    def _read_parsed(self, statement: Select) -> ParsedDocument | None:
        with self.engine.connect() as connection:
            document_row = connection.execute(statement).mappings().one_or_none()
            if document_row is None:
                return None
            page_rows = (
                connection.execute(
                    select(parsed_pages)
                    .where(parsed_pages.c.parsed_document_id == document_row["parsed_document_id"])
                    .order_by(parsed_pages.c.page_number)
                )
                .mappings()
                .all()
            )
        return self._parsed_from_rows(document_row, page_rows)

    @staticmethod
    def _source_from_row(row: RowMapping) -> SourceDocument:
        values = dict(row)
        values["discovered_at"] = datetime.fromisoformat(values["discovered_at"])
        return SourceDocument.model_validate(values)

    @staticmethod
    def _version_from_row(row: RowMapping) -> DocumentVersion:
        values = dict(row)
        values["retrieved_at"] = datetime.fromisoformat(values["retrieved_at"])
        return DocumentVersion.model_validate(values)

    @staticmethod
    def _parsed_from_rows(document_row: RowMapping, page_rows: list[RowMapping]) -> ParsedDocument:
        values = dict(document_row)
        values.pop("configuration_hash")
        values["warnings"] = tuple(json.loads(values.pop("warnings_json")))
        values["created_at"] = datetime.fromisoformat(values["created_at"])
        values["pages"] = tuple(
            ParsedPage(
                page_number=row["page_number"],
                text=row["text"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                quality=TextQuality(
                    character_count=row["character_count"],
                    non_whitespace_count=row["non_whitespace_count"],
                    alphanumeric_ratio=row["alphanumeric_ratio"],
                    replacement_character_ratio=row["replacement_character_ratio"],
                ),
                used_ocr=row["used_ocr"],
            )
            for row in page_rows
        )
        return ParsedDocument.model_validate(values)
