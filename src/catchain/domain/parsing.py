"""Parsed PDF text, quality, and provenance models."""

from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from catchain.domain.common import ImmutableDomainModel


class TextQuality(ImmutableDomainModel):
    """Deterministic measurements used to decide whether text needs OCR."""

    character_count: int = Field(ge=0)
    non_whitespace_count: int = Field(ge=0)
    alphanumeric_ratio: float = Field(ge=0, le=1)
    replacement_character_ratio: float = Field(ge=0, le=1)


class ParsedPage(ImmutableDomainModel):
    """Final text and traceability metadata for one PDF page."""

    page_number: int = Field(ge=1)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    quality: TextQuality
    used_ocr: bool = False

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if self.char_start != 0 or self.char_end != len(self.text):
            raise ValueError("offsets must span page text")
        return self


class ParsedDocument(ImmutableDomainModel):
    """Reproducible page text derived from one immutable document version."""

    parsed_document_id: UUID = Field(default_factory=uuid4)
    document_version_id: UUID
    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    ocr_engine_name: str | None = Field(default=None, min_length=1)
    ocr_engine_version: str | None = Field(default=None, min_length=1)
    pages: tuple[ParsedPage, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_pages_and_ocr_provenance(self) -> Self:
        page_numbers = [page.page_number for page in self.pages]
        if page_numbers != list(range(1, len(self.pages) + 1)):
            raise ValueError("page numbers must be sequential and one-based")
        if (self.ocr_engine_name is None) != (self.ocr_engine_version is None):
            raise ValueError("OCR engine name and version must be provided together")
        if any(page.used_ocr for page in self.pages) and self.ocr_engine_name is None:
            raise ValueError("OCR pages require engine provenance")
        return self
