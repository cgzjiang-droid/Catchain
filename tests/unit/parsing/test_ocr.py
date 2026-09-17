from pathlib import Path

import pymupdf
import pytest

from catchain.parsing.ocr import (
    OcrExecutionError,
    OcrToolUnavailableError,
    TesseractOcrAdapter,
)


def create_one_page_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.draw_rect(
        pymupdf.Rect(100, 100, 400, 400),
        color=(0, 0, 0),
        fill=(0, 0, 0),
    )
    document.save(path)
    document.close()


def make_fake_tesseract(path: Path, *, ocr_output: str) -> None:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        '  echo "tesseract 5.4.0"\n'
        "else\n"
        f"  printf '%s' '{ocr_output}'\n"
        "fi\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_tesseract_adapter_reports_missing_executable(tmp_path: Path) -> None:
    adapter = TesseractOcrAdapter(executable=str(tmp_path / "missing-tesseract"))

    with pytest.raises(OcrToolUnavailableError, match="Tesseract executable not found"):
        _ = adapter.version


def test_tesseract_adapter_renders_page_and_returns_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    executable = tmp_path / "fake-tesseract"
    create_one_page_pdf(pdf_path)
    make_fake_tesseract(executable, ocr_output="recognized text")
    adapter = TesseractOcrAdapter(executable=str(executable))

    assert adapter.version == "5.4.0"
    assert adapter.extract_page(pdf_path, page_number=1) == "recognized text"


def test_tesseract_adapter_rejects_empty_ocr_result(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    executable = tmp_path / "fake-tesseract"
    create_one_page_pdf(pdf_path)
    make_fake_tesseract(executable, ocr_output="")
    adapter = TesseractOcrAdapter(executable=str(executable))

    with pytest.raises(OcrExecutionError, match="returned no text"):
        adapter.extract_page(pdf_path, page_number=1)
