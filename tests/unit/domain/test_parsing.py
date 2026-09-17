from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from catchain.domain import ParsedDocument, ParsedPage, TextQuality


def quality(character_count: int) -> TextQuality:
    return TextQuality(
        character_count=character_count,
        non_whitespace_count=character_count,
        alphanumeric_ratio=1.0 if character_count else 0.0,
        replacement_character_ratio=0.0,
    )


def page(page_number: int, text: str, *, used_ocr: bool = False) -> ParsedPage:
    return ParsedPage(
        page_number=page_number,
        text=text,
        char_start=0,
        char_end=len(text),
        quality=quality(len(text)),
        used_ocr=used_ocr,
    )


def test_parsed_document_accepts_traceable_native_pages() -> None:
    document = ParsedDocument(
        document_version_id=UUID("11111111-1111-1111-1111-111111111111"),
        parser_name="PyMuPDF",
        parser_version="1.26.0",
        pages=(page(1, "first page"), page(2, "second page")),
        created_at=datetime(2026, 9, 14, tzinfo=UTC),
    )

    assert [item.page_number for item in document.pages] == [1, 2]
    assert document.ocr_engine_name is None


def test_parsed_page_rejects_zero_based_page_number() -> None:
    with pytest.raises(ValidationError):
        page(0, "text")


def test_parsed_page_rejects_offsets_that_do_not_span_its_text() -> None:
    with pytest.raises(ValidationError, match="offsets must span page text"):
        ParsedPage(
            page_number=1,
            text="text",
            char_start=0,
            char_end=3,
            quality=quality(4),
        )


def test_parsed_document_requires_sequential_pages() -> None:
    with pytest.raises(ValidationError, match="sequential"):
        ParsedDocument(
            document_version_id=UUID("11111111-1111-1111-1111-111111111111"),
            parser_name="PyMuPDF",
            parser_version="1.26.0",
            pages=(page(1, "first"), page(3, "third")),
            created_at=datetime(2026, 9, 14, tzinfo=UTC),
        )


def test_parsed_document_requires_ocr_provenance_for_ocr_pages() -> None:
    with pytest.raises(ValidationError, match="OCR pages require engine provenance"):
        ParsedDocument(
            document_version_id=UUID("11111111-1111-1111-1111-111111111111"),
            parser_name="PyMuPDF",
            parser_version="1.26.0",
            pages=(page(1, "OCR text", used_ocr=True),),
            created_at=datetime(2026, 9, 14, tzinfo=UTC),
        )


def test_parsed_document_requires_paired_ocr_provenance() -> None:
    with pytest.raises(ValidationError, match="provided together"):
        ParsedDocument(
            document_version_id=UUID("11111111-1111-1111-1111-111111111111"),
            parser_name="PyMuPDF",
            parser_version="1.26.0",
            ocr_engine_name="Tesseract",
            pages=(page(1, "OCR text", used_ocr=True),),
            created_at=datetime(2026, 9, 14, tzinfo=UTC),
        )


def test_parsed_document_requires_timezone_and_is_immutable() -> None:
    with pytest.raises(ValidationError):
        ParsedDocument(
            document_version_id=UUID("11111111-1111-1111-1111-111111111111"),
            parser_name="PyMuPDF",
            parser_version="1.26.0",
            pages=(page(1, "text"),),
            created_at=datetime(2026, 9, 14),
        )

    valid = ParsedDocument(
        document_version_id=UUID("11111111-1111-1111-1111-111111111111"),
        parser_name="PyMuPDF",
        parser_version="1.26.0",
        pages=(page(1, "text"),),
        created_at=datetime(2026, 9, 14, tzinfo=UTC),
    )
    with pytest.raises(ValidationError, match="frozen_instance"):
        valid.parser_name = "other"
