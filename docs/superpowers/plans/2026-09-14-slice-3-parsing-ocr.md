# Slice 3 PDF Parsing and OCR Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert immutable Raw PDFs into traceable per-page text, measure text quality, and use Tesseract OCR only for pages that fail deterministic quality checks.

**Architecture:** Immutable Parsed-layer domain models describe page text, offsets, quality, parser provenance, and OCR provenance. A PyMuPDF adapter extracts native text. A deterministic policy selects low-quality pages for an OCR adapter, then a parsing service produces one reproducible `ParsedDocument` without modifying Raw bytes.

**Tech Stack:** Python 3.12+, Pydantic 2, PyMuPDF, Tesseract CLI, pytest, Ruff

**Spec:** `docs/superpowers/specs/2026-09-09-catchain-redesign.md`

## Global Constraints

- Raw files remain immutable.
- Page numbers are one-based.
- Character offsets describe positions within each page's text.
- Parser and OCR engine names and versions are recorded.
- OCR routing uses deterministic quality rules, not an LLM decision.
- A genuinely blank page is preserved as blank instead of being sent to OCR.
- Native PDF text is kept for pages that pass quality checks.
- Missing tools and invalid PDFs produce typed failures rather than empty success results.
- Tests use generated, non-private PDF fixtures.
- No registry network call, LLM extraction, scoring, RAG, or agent framework enters this slice.

---

### Task 1: Define Parsed-Layer Contracts

**Files:**

- Create: `src/catchain/domain/parsing.py`
- Modify: `src/catchain/domain/__init__.py`
- Modify: `src/catchain/schema_export.py`
- Test: `tests/unit/domain/test_parsing.py`
- Modify: `schemas/generated/*.schema.json`

**Interfaces:**

- Produces: `TextQuality`, `ParsedPage`, and `ParsedDocument` immutable Pydantic models.
- `ParsedPage` contains one-based page number, text, page-local offsets, quality, and whether OCR supplied the final text.
- `ParsedDocument` contains document-version identity, parser provenance, optional OCR provenance, pages, warnings, and creation time.

- [x] **Step 1: Write failing model tests**

  Verify valid construction, immutability, one-based pages, paired ordered offsets, unique sequential page numbers, timezone-aware creation, and the rule that OCR pages require OCR engine provenance.

- [x] **Step 2: Run tests and verify RED**

  Expected: import failure because parsing models do not exist.

- [x] **Step 3: Implement the minimal Pydantic contracts**

  Use the existing immutable base model and explicit cross-field validators. Reject unknown fields.

- [x] **Step 4: Export public models and generated JSON Schema**

  Add `ParsedDocument` to deterministic schema generation and regenerate committed schemas.

- [x] **Step 5: Run focused tests, all tests, Ruff, and schema stability checks**

- [x] **Step 6: Record the product meaning and commit**

### Task 2: Extract Native PDF Text with PyMuPDF

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/catchain/parsing/__init__.py`
- Create: `src/catchain/parsing/pymupdf_parser.py`
- Test: `tests/unit/parsing/test_pymupdf_parser.py`

**Interfaces:**

- Produces: `PyMuPdfParser.parse(path: Path, document_version_id: UUID) -> ParsedDocument`.
- Records PyMuPDF version, per-page native text, sequential combined offsets, and quality measurements.

- [x] **Step 1: Add the bounded PyMuPDF dependency**
- [x] **Step 2: Write a generated two-page PDF behavior test**
- [x] **Step 3: Run the test and verify RED**
- [x] **Step 4: Implement native page extraction and quality measurements**
- [x] **Step 5: Test invalid PDF failure and verify all checks**
- [x] **Step 6: Update the learning journal and commit**

### Task 3: Add Deterministic OCR Routing and Tesseract Adapter

**Files:**

- Create: `src/catchain/parsing/quality.py`
- Create: `src/catchain/parsing/ocr.py`
- Create: `src/catchain/parsing/service.py`
- Test: `tests/unit/parsing/test_quality.py`
- Test: `tests/integration/parsing/test_ocr_fallback.py`

**Interfaces:**

- Produces: `TextQualityPolicy.requires_ocr(page: ParsedPage) -> bool`.
- Uses a deterministic rendered-page signal to distinguish blank pages from scanned
  pages with meaningful visual content.
- Produces: `OcrAdapter.extract_page(pdf_path: Path, page_number: int) -> str` protocol and `TesseractOcrAdapter` implementation.
- Produces: `parse_with_ocr_fallback(...) -> ParsedDocument` that replaces only selected low-quality page text and records OCR provenance.

- [x] **Step 1: Write failing threshold tests using boundary values**
- [x] **Step 2: Implement minimum non-whitespace and replacement-character rules**
- [x] **Step 2a: Test and implement blank-versus-visual-content routing**
- [x] **Step 3: Write failing OCR-routing integration tests with a deterministic fake adapter**
- [x] **Step 4: Implement page-level fallback and Tesseract command adapter**
- [x] **Step 5: Verify Tesseract absence produces a typed actionable failure**
- [x] **Step 6: Run all tests and Ruff, update the journal, and commit**

### Task 4: Persist and Expose Parsed Results

**Files:**

- Modify: `src/catchain/storage/database.py`
- Modify: `src/catchain/storage/document_repository.py`
- Create: `migrations/versions/0002_parsed_documents.py`
- Modify: `src/catchain/cli.py`
- Modify: `README.md`
- Create: `docs/learning/03-pdf-parsing-ocr-fallback.md`
- Test: `tests/integration/parsing/test_parsed_repository.py`
- Test: `tests/integration/test_parse_cli.py`

**Interfaces:**

- Stores and reconstructs `ParsedDocument` records keyed by document version and parser configuration.
- Exposes `catchain parse raw` with Raw root, database, document-version ID, and OCR policy options.

- [x] **Step 1: Write failing migration and repository tests**
- [x] **Step 2: Implement parsed tables, migration, and repository methods**
- [x] **Step 3: Write a failing CLI behavior test**
- [x] **Step 4: Implement the parse command and structured failure output**
- [x] **Step 5: Render the generated PDF fixture and visually verify both pages**
- [x] **Step 6: Write the Slice 3 lesson and README flow**
- [x] **Step 7: Run all tests, Ruff, migrations, schema regeneration, and a real CLI parse**
- [x] **Step 8: Commit the verified Slice 3 user flow**
