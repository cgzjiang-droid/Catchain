from pathlib import Path
from uuid import UUID

import pymupdf
import pytest

from catchain.parsing.pymupdf_parser import PdfParseError, PyMuPdfParser

DOCUMENT_VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")


def create_two_page_pdf(path: Path) -> None:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "First project page")
    document.new_page().insert_text((72, 72), "Second monitoring page")
    document.save(path)
    document.close()


def test_parser_extracts_traceable_text_from_each_pdf_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "project.pdf"
    create_two_page_pdf(pdf_path)

    parsed = PyMuPdfParser().parse(pdf_path, DOCUMENT_VERSION_ID)

    assert parsed.document_version_id == DOCUMENT_VERSION_ID
    assert parsed.parser_name == "PyMuPDF"
    assert parsed.parser_version == pymupdf.version[0]
    assert [page.page_number for page in parsed.pages] == [1, 2]
    assert parsed.pages[0].text == "First project page\n"
    assert parsed.pages[1].text == "Second monitoring page\n"
    assert parsed.pages[0].char_end == len(parsed.pages[0].text)
    assert parsed.pages[0].quality.non_whitespace_count == 16
    assert all(page.used_ocr is False for page in parsed.pages)


def test_parser_rejects_invalid_pdf_bytes(tmp_path: Path) -> None:
    invalid_pdf = tmp_path / "invalid.pdf"
    invalid_pdf.write_bytes(b"not a pdf")

    with pytest.raises(PdfParseError, match="cannot parse PDF"):
        PyMuPdfParser().parse(invalid_pdf, DOCUMENT_VERSION_ID)
