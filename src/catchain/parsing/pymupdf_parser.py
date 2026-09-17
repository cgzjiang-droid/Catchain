"""Native page-text extraction with PyMuPDF."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pymupdf

from catchain.domain import ParsedDocument, ParsedPage
from catchain.parsing.quality import measure_text_quality


class PdfParseError(ValueError):
    """A source cannot be opened as a readable PDF."""


class PyMuPdfParser:
    """Extract native text and deterministic quality measurements per page."""

    name = "PyMuPDF"

    def parse(self, pdf_path: Path, document_version_id: UUID) -> ParsedDocument:
        pdf_path = Path(pdf_path)
        try:
            document = pymupdf.open(pdf_path)
        except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
            raise PdfParseError(f"cannot parse PDF: {pdf_path}") from error

        try:
            pages = tuple(
                self._parse_page(page, page_number=index)
                for index, page in enumerate(document, start=1)
            )
        finally:
            document.close()

        return ParsedDocument(
            document_version_id=document_version_id,
            parser_name=self.name,
            parser_version=pymupdf.version[0],
            pages=pages,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _parse_page(page: pymupdf.Page, *, page_number: int) -> ParsedPage:
        text = page.get_text()
        return ParsedPage(
            page_number=page_number,
            text=text,
            char_start=0,
            char_end=len(text),
            quality=measure_text_quality(text),
        )
