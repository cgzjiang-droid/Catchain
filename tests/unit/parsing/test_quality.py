from pathlib import Path

import pymupdf

from catchain.domain import ParsedPage, TextQuality
from catchain.parsing.quality import RenderedPageInspector, TextQualityPolicy


def page(*, non_whitespace_count: int, replacement_ratio: float = 0.0) -> ParsedPage:
    text = "x" * non_whitespace_count
    return ParsedPage(
        page_number=1,
        text=text,
        char_start=0,
        char_end=len(text),
        quality=TextQuality(
            character_count=len(text),
            non_whitespace_count=non_whitespace_count,
            alphanumeric_ratio=1.0 if text else 0.0,
            replacement_character_ratio=replacement_ratio,
        ),
    )


def test_quality_policy_routes_text_below_minimum_to_ocr() -> None:
    policy = TextQualityPolicy(min_non_whitespace_count=80)

    assert policy.requires_ocr(page(non_whitespace_count=79)) is True
    assert policy.requires_ocr(page(non_whitespace_count=80)) is False


def test_quality_policy_routes_only_replacement_ratios_above_limit() -> None:
    policy = TextQualityPolicy(
        min_non_whitespace_count=0,
        max_replacement_character_ratio=0.02,
    )

    assert policy.requires_ocr(page(non_whitespace_count=100, replacement_ratio=0.02)) is False
    assert policy.requires_ocr(page(non_whitespace_count=100, replacement_ratio=0.021)) is True


def test_rendered_page_inspector_distinguishes_blank_and_visual_content(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "blank-and-scan.pdf"
    document = pymupdf.open()
    document.new_page()
    visual_page = document.new_page()
    visual_page.draw_rect(pymupdf.Rect(100, 100, 400, 400), color=(0, 0, 0), fill=(0, 0, 0))
    document.save(pdf_path)
    document.close()

    inspector = RenderedPageInspector()

    assert inspector.has_meaningful_content(pdf_path, page_number=1) is False
    assert inspector.has_meaningful_content(pdf_path, page_number=2) is True
