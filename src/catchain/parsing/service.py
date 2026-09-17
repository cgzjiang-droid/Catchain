"""Native PDF parsing with selective page-level OCR fallback."""

from pathlib import Path
from uuid import UUID

from catchain.domain import ParsedDocument, ParsedPage
from catchain.parsing.ocr import OcrAdapter
from catchain.parsing.pymupdf_parser import PyMuPdfParser
from catchain.parsing.quality import (
    RenderedPageInspector,
    TextQualityPolicy,
    measure_text_quality,
)


def parse_with_ocr_fallback(
    pdf_path: Path,
    document_version_id: UUID,
    *,
    ocr_adapter: OcrAdapter,
    quality_policy: TextQualityPolicy | None = None,
    page_inspector: RenderedPageInspector | None = None,
    native_parser: PyMuPdfParser | None = None,
) -> ParsedDocument:
    """Keep good native text, OCR meaningful low-text pages, and preserve blanks."""
    policy = quality_policy or TextQualityPolicy()
    inspector = page_inspector or RenderedPageInspector()
    parser = native_parser or PyMuPdfParser()
    native_document = parser.parse(Path(pdf_path), document_version_id)

    final_pages: list[ParsedPage] = []
    warnings = list(native_document.warnings)
    used_ocr = False

    for page in native_document.pages:
        if not policy.requires_ocr(page):
            final_pages.append(page)
            continue

        if not inspector.has_meaningful_content(
            Path(pdf_path), page_number=page.page_number
        ):
            final_pages.append(page)
            warnings.append(f"page {page.page_number}: blank page skipped OCR")
            continue

        ocr_text = ocr_adapter.extract_page(Path(pdf_path), page.page_number)
        final_pages.append(
            ParsedPage(
                page_number=page.page_number,
                text=ocr_text,
                char_start=0,
                char_end=len(ocr_text),
                quality=measure_text_quality(ocr_text),
                used_ocr=True,
            )
        )
        used_ocr = True

    return ParsedDocument(
        parsed_document_id=native_document.parsed_document_id,
        document_version_id=native_document.document_version_id,
        parser_name=native_document.parser_name,
        parser_version=native_document.parser_version,
        ocr_engine_name=ocr_adapter.name if used_ocr else None,
        ocr_engine_version=ocr_adapter.version if used_ocr else None,
        pages=tuple(final_pages),
        warnings=tuple(warnings),
        created_at=native_document.created_at,
    )
