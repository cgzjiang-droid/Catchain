# Slice 2 Raw Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import local source files into an immutable Raw layer, identify identical bytes with SHA-256, preserve document versions, and persist traceable metadata in SQLite.

**Architecture:** A filesystem `RawBlobStore` owns immutable content-addressed bytes. An ingestion service combines stored bytes with existing `SourceDocument` and `DocumentVersion` domain contracts. A SQLAlchemy repository persists metadata and enforces deduplication, while the CLI exposes a small local-import flow.

**Tech Stack:** Python 3.12+, pathlib/hashlib, Pydantic 2, SQLAlchemy 2, Alembic, SQLite, Typer, pytest, Ruff

**Spec:** `docs/superpowers/specs/2026-09-09-catchain-redesign.md`

## Global Constraints

- Raw bytes are immutable and never silently overwritten.
- SHA-256 is computed from file bytes and uses 64 lowercase hexadecimal characters.
- Re-importing identical bytes reuses the existing Raw blob.
- A new content hash creates a new `DocumentVersion`; it does not replace history.
- SQLite writes are behind a repository interface.
- Local test fixtures contain no private project data.
- No registry network call, PDF parsing, OCR, LLM call, scoring, RAG, or agent framework enters this slice.
- Every production behavior is introduced by a failing test.

---

### Task 1: Store Immutable Raw Blobs

**Files:**

- Create: `src/catchain/ingestion/__init__.py`
- Create: `src/catchain/ingestion/raw_store.py`
- Test: `tests/unit/ingestion/test_raw_store.py`

**Interfaces:**

- Consumes: `Path` to a readable, non-empty local file and a Raw root directory.
- Produces: `StoredRawBlob(sha256: str, byte_size: int, path: Path, created: bool)` from `RawBlobStore.store_file(source: Path)`.

- [x] **Step 1: Write failing tests for immutable storage and deduplication**

  Test that known bytes produce the expected lowercase SHA-256, are copied unchanged below the Raw root, and return `created=True`. Import the same bytes again and assert the same path and `created=False`. Test that empty and missing files are rejected.

- [x] **Step 2: Run the focused test and verify RED**

  Run `UV_PROJECT_ENVIRONMENT=venv uv run pytest tests/unit/ingestion/test_raw_store.py -v`.

  Expected: collection fails because `catchain.ingestion.raw_store` does not exist.

- [x] **Step 3: Implement the minimal content-addressed store**

  Stream the source through `hashlib.sha256`, stage it inside the Raw root, and place it at `<raw-root>/<first-two-hash-characters>/<sha256>`. Reuse an existing destination without rewriting it. Reject missing, non-file, and empty inputs with explicit exceptions.

- [x] **Step 4: Verify GREEN and run static checks**

  Run the focused test, the complete test suite, and `uv run ruff check .`.

- [x] **Step 5: Record the product meaning and commit**

  Add observed RED/GREEN results and a plain-language explanation of Raw immutability, hashing, and deduplication to `docs/learning/development-journal.md`. Commit only Task 1 files.

### Task 2: Persist Document Metadata and Versions in SQLite

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/catchain/storage/__init__.py`
- Create: `src/catchain/storage/database.py`
- Create: `src/catchain/storage/document_repository.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/0001_documents.py`
- Test: `tests/integration/storage/test_document_repository.py`

**Interfaces:**

- Consumes: validated `SourceDocument` and `DocumentVersion` objects.
- Produces: `DocumentRepository.add_source`, `get_source`, `add_version`, `list_versions`, and `find_version_by_hash`.

- [x] **Step 1: Add SQLAlchemy and Alembic dependency ranges**

  Add `sqlalchemy>=2.0,<3` and `alembic>=1.14,<2`, then refresh `uv.lock`.

- [x] **Step 2: Write repository integration tests**

  Verify round-trip persistence, chronological version history, and uniqueness of `(source_document_id, sha256)`.

- [x] **Step 3: Run the integration tests and verify RED**

  Expected: import failure because the storage package does not exist.

- [x] **Step 4: Implement tables, migration, and repository**

  Store UUIDs and aware timestamps as strings, enum values as their stable string values, and preserve all fields required to reconstruct the Pydantic models. Raise a typed duplicate-version result instead of silently inserting a duplicate row.

- [x] **Step 5: Run migration and repository verification**

  Apply the migration to a temporary SQLite database, run integration tests, the full test suite, and Ruff.

- [x] **Step 6: Update the learning journal and commit**

  Record SQLite, repository boundaries, migration purpose, and the observed verification output.

### Task 3: Build the Local Document Ingestion Service

**Files:**

- Create: `src/catchain/ingestion/service.py`
- Test: `tests/integration/ingestion/test_local_ingestion.py`

**Interfaces:**

- Consumes: a validated `SourceDocument`, local file path, content type, retrieval time, `RawBlobStore`, and `DocumentRepository`.
- Produces: `IngestionResult(document_version: DocumentVersion, raw_path: Path, duplicate: bool)`.

- [x] **Step 1: Write an end-to-end failing ingestion test**

  Verify first import stores bytes and one version, identical re-import returns the existing version, and changed bytes create a second version without deleting the first.

- [x] **Step 2: Run the test and verify RED**

  Expected: import failure because `catchain.ingestion.service` does not exist.

- [x] **Step 3: Implement the ingestion transaction**

  Store the Raw blob, check the repository by source-document identity and content hash, create a `DocumentVersion` only when the content is new, and return a structured result.

- [x] **Step 4: Verify integration and failure behavior**

  Run focused integration tests, all tests, and Ruff. Confirm changed content creates history and repeated content does not.

- [x] **Step 5: Update the learning journal and commit**

  Explain idempotency, document identity versus content identity, and version preservation using the observed test scenario.

### Task 4: Expose and Document the MVP Import Flow

**Files:**

- Modify: `src/catchain/cli.py`
- Modify: `README.md`
- Create: `docs/learning/02-raw-ingestion-versioning.md`
- Test: `tests/integration/test_ingest_cli.py`

**Interfaces:**

- Consumes: local file plus registry, project identifier, source URL, document type, content type, Raw root, and SQLite path.
- Produces: a concise import result showing document-version identity, SHA-256, byte size, stored Raw path, and whether content was deduplicated.

- [x] **Step 1: Write a failing CLI test**

  Import a small licensed fixture twice and assert the second command reports reuse without adding a duplicate version.

- [x] **Step 2: Run the test and verify RED**

  Expected: Typer reports that the `ingest local` command does not exist.

- [x] **Step 3: Implement the CLI command**

  Validate arguments through existing domain models, call the ingestion service, and print traceable output without exposing document contents.

- [x] **Step 4: Write the Slice 2 lesson and README instructions**

  Explain the product problem, inputs, outputs, failure modes, hashing, idempotency, SQLite, versioning, interview questions, and minimum product-manager explanation.

- [x] **Step 5: Run final Slice 2 verification**

  Run `uv sync --dev`, all tests, Ruff, schema regeneration, a temporary CLI import twice, `git diff --check`, and inspect `git status --short`.

- [x] **Step 6: Commit the CLI and learning artifact**

  Commit the verified user flow and documentation as the final Slice 2 task.
