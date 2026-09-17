from pathlib import Path
from uuid import UUID

import pymupdf

from catchain.parsing import RenderedPageInspector, TextQualityPolicy
from catchain.parsing.service import parse_with_ocr_fallback

DOCUMENT_VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeOcrAdapter:
    name = "Fake OCR"
    version = "test-1"

    def __init__(self) -> None:
        self.page_calls: list[int] = []

    def extract_page(self, pdf_path: Path, page_number: int) -> str:
        self.page_calls.append(page_number)
        return f"OCR recovered page {page_number}"


def create_native_visual_and_blank_pdf(path: Path) -> None:
    document = pymupdf.open()
    native_page = document.new_page()
    native_page.insert_text((72, 72), "Native project text remains unchanged")
    visual_page = document.new_page()
    visual_page.draw_rect(
        pymupdf.Rect(100, 100, 400, 400),
        color=(0, 0, 0),
        fill=(0, 0, 0),
    )
    document.new_page()
    document.save(path)
    document.close()


def test_ocr_fallback_replaces_only_low_text_pages_with_visual_content(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    create_native_visual_and_blank_pdf(pdf_path)
    ocr = FakeOcrAdapter()

    parsed = parse_with_ocr_fallback(
        pdf_path,
        DOCUMENT_VERSION_ID,
        ocr_adapter=ocr,
        quality_policy=TextQualityPolicy(min_non_whitespace_count=20),
        page_inspector=RenderedPageInspector(),
    )

    assert ocr.page_calls == [2]
    assert parsed.pages[0].text == "Native project text remains unchanged\n"
    assert parsed.pages[0].used_ocr is False
    assert parsed.pages[1].text == "OCR recovered page 2"
    assert parsed.pages[1].used_ocr is True
    assert parsed.pages[2].text == ""
    assert parsed.pages[2].used_ocr is False
    assert parsed.ocr_engine_name == "Fake OCR"
    assert parsed.ocr_engine_version == "test-1"
    assert "page 3: blank page skipped OCR" in parsed.warnings
