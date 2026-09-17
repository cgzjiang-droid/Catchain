"""OCR adapter contract and Tesseract command implementation."""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import pymupdf


class OcrError(RuntimeError):
    """Base failure for OCR operations."""


class OcrToolUnavailableError(OcrError):
    """The configured OCR executable cannot be started."""


class OcrExecutionError(OcrError):
    """The OCR engine ran but did not produce a usable result."""


class OcrAdapter(Protocol):
    """Page-level OCR boundary used by the parsing service."""

    name: str

    @property
    def version(self) -> str: ...

    def extract_page(self, pdf_path: Path, page_number: int) -> str: ...


class TesseractOcrAdapter:
    """Render one PDF page and send it to the local Tesseract CLI."""

    name = "Tesseract"

    def __init__(
        self,
        *,
        executable: str = "tesseract",
        language: str = "eng",
        dpi: int = 300,
        timeout_seconds: float = 120,
    ) -> None:
        self.executable = executable
        self.language = language
        self.dpi = dpi
        self.timeout_seconds = timeout_seconds
        self._version: str | None = None

    @property
    def version(self) -> str:
        if self._version is None:
            result = self._run([self.executable, "--version"])
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
            parts = first_line.split(maxsplit=1)
            if len(parts) != 2 or not parts[1]:
                raise OcrExecutionError("Tesseract returned an unreadable version")
            self._version = parts[1]
        return self._version

    def extract_page(self, pdf_path: Path, page_number: int) -> str:
        if page_number < 1:
            raise ValueError("page number must be one-based")

        with pymupdf.open(Path(pdf_path)) as document:
            if page_number > document.page_count:
                raise ValueError("page number exceeds PDF page count")
            page = document.load_page(page_number - 1)
            scale = self.dpi / 72
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)

        with TemporaryDirectory(prefix="catchain-ocr-") as temp_dir:
            image_path = Path(temp_dir) / f"page-{page_number}.png"
            pixmap.save(image_path)
            result = self._run(
                [
                    self.executable,
                    str(image_path),
                    "stdout",
                    "-l",
                    self.language,
                ]
            )

        text = result.stdout.strip()
        if not text:
            raise OcrExecutionError(
                f"Tesseract returned no text for page {page_number}"
            )
        return text

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as error:
            raise OcrToolUnavailableError(
                f"Tesseract executable not found: {self.executable}. "
                "Install Tesseract or configure its executable path."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise OcrExecutionError(
                f"Tesseract exceeded the {self.timeout_seconds:g}-second timeout"
            ) from error

        if result.returncode != 0:
            detail = result.stderr.strip() or "no error detail"
            raise OcrExecutionError(
                f"Tesseract failed with exit code {result.returncode}: {detail}"
            )
        return result
