"""Deterministic text-quality measurement and OCR routing."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from catchain.domain import ParsedPage, TextQuality


def measure_text_quality(text: str) -> TextQuality:
    """Measure text without model judgment or document-specific heuristics."""
    character_count = len(text)
    non_whitespace_count = sum(not character.isspace() for character in text)
    alphanumeric_count = sum(character.isalnum() for character in text)
    replacement_count = text.count("\ufffd")
    return TextQuality(
        character_count=character_count,
        non_whitespace_count=non_whitespace_count,
        alphanumeric_ratio=(
            alphanumeric_count / non_whitespace_count if non_whitespace_count else 0
        ),
        replacement_character_ratio=(
            replacement_count / character_count if character_count else 0
        ),
    )


@dataclass(frozen=True)
class TextQualityPolicy:
    """Select native-text pages that need a second extraction attempt."""

    min_non_whitespace_count: int = 80
    max_replacement_character_ratio: float = 0.02

    def __post_init__(self) -> None:
        if self.min_non_whitespace_count < 0:
            raise ValueError("minimum non-whitespace count cannot be negative")
        if not 0 <= self.max_replacement_character_ratio <= 1:
            raise ValueError("maximum replacement-character ratio must be between 0 and 1")

    def requires_ocr(self, page: ParsedPage) -> bool:
        return (
            page.quality.non_whitespace_count < self.min_non_whitespace_count
            or page.quality.replacement_character_ratio
            > self.max_replacement_character_ratio
        )


@dataclass(frozen=True)
class RenderedPageInspector:
    """Detect visible page content with a small deterministic grayscale render."""

    dpi: int = 36
    white_threshold: int = 245
    min_ink_ratio: float = 0.001

    def __post_init__(self) -> None:
        if self.dpi <= 0:
            raise ValueError("DPI must be positive")
        if not 0 <= self.white_threshold <= 255:
            raise ValueError("white threshold must be between 0 and 255")
        if not 0 <= self.min_ink_ratio <= 1:
            raise ValueError("minimum ink ratio must be between 0 and 1")

    def has_meaningful_content(self, pdf_path: Path, *, page_number: int) -> bool:
        """Return whether a one-based page contains enough non-white pixels."""
        if page_number < 1:
            raise ValueError("page number must be one-based")

        with pymupdf.open(Path(pdf_path)) as document:
            if page_number > document.page_count:
                raise ValueError("page number exceeds PDF page count")
            page = document.load_page(page_number - 1)
            scale = self.dpi / 72
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                colorspace=pymupdf.csGRAY,
                alpha=False,
            )

        samples = pixmap.samples
        ink_count = sum(value < self.white_threshold for value in samples)
        return ink_count / len(samples) >= self.min_ink_ratio
