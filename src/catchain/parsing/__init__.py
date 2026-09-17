"""PDF parsing and OCR fallback."""

from catchain.parsing.ocr import (
    OcrAdapter,
    OcrError,
    OcrExecutionError,
    OcrToolUnavailableError,
    TesseractOcrAdapter,
)
from catchain.parsing.pymupdf_parser import PdfParseError, PyMuPdfParser
from catchain.parsing.quality import (
    RenderedPageInspector,
    TextQualityPolicy,
    measure_text_quality,
)
from catchain.parsing.service import parse_with_ocr_fallback

__all__ = [
    "OcrAdapter",
    "OcrError",
    "OcrExecutionError",
    "OcrToolUnavailableError",
    "PdfParseError",
    "PyMuPdfParser",
    "RenderedPageInspector",
    "TesseractOcrAdapter",
    "TextQualityPolicy",
    "measure_text_quality",
    "parse_with_ocr_fallback",
]
