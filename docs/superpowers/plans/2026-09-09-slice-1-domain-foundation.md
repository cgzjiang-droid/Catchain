# Slice 1 Domain Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a runnable, tested CATchain Python package whose first domain models represent document identity, document versions, field evidence, and pipeline runs, and whose Pydantic models generate committed JSON Schemas.

**Architecture:** This slice creates only the domain foundation and a schema-export CLI. Immutable Pydantic models define the in-memory contracts; JSON Schema is generated from those models, so there is one source of truth. No database, PDF parsing, registry networking, OCR, LLM call, scoring logic, or agent behavior is included in this slice.

**Tech Stack:** Python 3.12+, uv, Pydantic 2, Typer, pytest, Ruff

**Spec:** `docs/superpowers/specs/2026-09-09-catchain-redesign.md`

## Global Constraints

- The implementation is a Python modular monolith.
- Python support is 3.12 or later.
- Pydantic models are the source of truth for runtime validation and generated JSON Schema.
- Source document and document-version models are immutable after construction.
- Model configuration rejects unknown fields instead of silently accepting them.
- SHA-256 values use exactly 64 lowercase hexadecimal characters.
- Timestamps must contain timezone information.
- Page numbers are one-based because they are user-facing evidence references.
- This slice contains no database, network call, PDF parsing, OCR, LLM call, scoring, RAG, or agent framework.
- Tests are written before their corresponding production implementation.
- On this macOS filesystem, run `export UV_PROJECT_ENVIRONMENT=venv` before uv commands because files created below a dot-prefixed virtual-environment directory inherit the hidden flag and Python skips hidden `.pth` files.
- Every technical concept explained during execution is recorded in `docs/learning/development-journal.md` before the corresponding task commit; verified material is then consolidated into the slice lesson.
- Each completed task is committed independently.

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, Python floor, dependencies, CLI entry point, pytest and Ruff configuration |
| `.gitignore` | Exclude environments, caches, runtime data, secrets, databases, and large generated artifacts |
| `README.md` | State the product boundary and provide the Slice 1 commands |
| `docs/learning/development-journal.md` | Chronological record of explanations, observed commands, failures, fixes, and learner questions |
| `src/catchain/__init__.py` | Publish the package version |
| `src/catchain/cli.py` | Own the Typer root command and schema-export subcommand |
| `src/catchain/domain/__init__.py` | Export the public domain-model API |
| `src/catchain/domain/common.py` | Shared immutable-model configuration and SHA-256 constrained type |
| `src/catchain/domain/documents.py` | Registry, document-type, source-document, and document-version models |
| `src/catchain/domain/evidence.py` | Page-level evidence-reference model and offset invariants |
| `src/catchain/domain/pipeline.py` | Pipeline-stage, status, and run models with lifecycle invariants |
| `src/catchain/schema_export.py` | Deterministically export JSON Schema for public domain models |
| `tests/unit/test_package.py` | Verify package import and version |
| `tests/unit/domain/test_documents.py` | Verify source and version models and invalid inputs |
| `tests/unit/domain/test_evidence.py` | Verify one-based pages and paired offsets |
| `tests/unit/domain/test_pipeline.py` | Verify valid and invalid pipeline lifecycle states |
| `tests/unit/test_schema_export.py` | Verify schema filenames, content, and deterministic reruns |
| `schemas/generated/*.schema.json` | Version-controlled schemas generated from Pydantic models |
| `docs/learning/01-domain-model-schema-validation.md` | Project-linked lesson covering domain models, structured data, schema, and validation |

---

### Task 1: Bootstrap the Python Package

**Files:**

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `docs/learning/development-journal.md`
- Create: `src/catchain/__init__.py`
- Create: `src/catchain/domain/__init__.py`
- Test: `tests/unit/test_package.py`

**Interfaces:**

- Consumes: Python 3.12 or later and the approved redesign specification.
- Produces: importable package `catchain`, constant `catchain.__version__: str`, and the `catchain` CLI entry-point declaration used in Task 4.

- [x] **Step 1: Verify and install the project manager**

Run:

```bash
uv --version
```

Expected before installation on the audited machine:

```text
command not found: uv
```

Install uv with the approved package manager:

```bash
brew install uv
uv --version
```

Expected after installation: a line beginning with `uv ` and a version number.

- [x] **Step 2: Write the failing package smoke test**

Create `tests/unit/test_package.py`:

```python
import importlib

import pytest


def test_package_exposes_version() -> None:
    try:
        catchain = importlib.import_module("catchain")
    except ModuleNotFoundError:
        pytest.fail("catchain package is not importable", pytrace=False)

    assert catchain.__version__ == "0.1.0"
```

- [x] **Step 3: Run the test and verify the expected failure**

Run:

```bash
python3 -m pytest tests/unit/test_package.py -v
```

Expected: FAIL with `catchain package is not importable` because the package does not exist yet.

- [x] **Step 4: Add project configuration**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "catchain"
version = "0.1.0"
description = "Traceable carbon document extraction and assessment system"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.10,<3",
  "typer>=0.15,<1",
]

[project.scripts]
catchain = "catchain.cli:app"

[dependency-groups]
dev = [
  "pytest>=8.3,<10",
  "ruff>=0.8,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Create `.gitignore`:

```gitignore
.worktrees/
.DS_Store
.env
.venv/
venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.py[cod]
*.sqlite
*.sqlite3

data/raw/
data/parsed/
data/extracted/

!.gitkeep
```

Create `README.md`:

````markdown
# CATchain

CATchain is a traceable carbon data engineering and AI structured-extraction system.
It preserves document identity and evidence before producing validated project records
and explainable assessments.

The current implementation is Slice 1: domain models and generated JSON Schema. It does
not yet contain registry networking, PDF parsing, OCR, LLM extraction, scoring, RAG, or
agent behavior.

## Development

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv sync --dev
uv run pytest
uv run ruff check .
uv run catchain schema export --output-dir schemas/generated
```

See `docs/superpowers/specs/2026-09-09-catchain-redesign.md` for the approved architecture.
````

Create `src/catchain/__init__.py`:

```python
"""CATchain package."""

__version__ = "0.1.0"
```

Create `src/catchain/domain/__init__.py`:

```python
"""Public domain models for CATchain."""
```

- [x] **Step 5: Create the locked environment and run the smoke test**

Run:

```bash
uv sync --dev
uv run pytest tests/unit/test_package.py -v
```

Expected: PASS. The command also creates `uv.lock`, which must be committed.

- [x] **Step 6: Run the initial static check**

Run:

```bash
uv run ruff check .
```

Expected: PASS with `All checks passed!`.

- [x] **Step 7: Commit the bootstrap**

Before committing, create `docs/learning/development-journal.md` and record the concepts already exercised in this task:

- Why feature work is isolated from `main` with a Git worktree.
- What a Python project environment and lockfile control.
- The RED, GREEN, and REFACTOR phases of TDD.
- The exact failing-test output and the exact passing-test output observed on this machine.
- Any command, error, or correction explained during the task.

Use dated headings and distinguish observed results from general explanations. Do not copy secrets, API keys, or private document contents into the journal.

```bash
git add pyproject.toml uv.lock .gitignore README.md src/catchain/__init__.py \
  src/catchain/domain/__init__.py tests/unit/test_package.py \
  docs/learning/development-journal.md
git commit -m "chore: bootstrap CATchain Python package"
```

---

### Task 2: Model Source Documents and Content Versions

**Files:**

- Create: `src/catchain/domain/common.py`
- Create: `src/catchain/domain/documents.py`
- Modify: `src/catchain/domain/__init__.py`
- Test: `tests/unit/domain/test_documents.py`

**Interfaces:**

- Consumes: Pydantic 2 and package foundation from Task 1.
- Produces: `Sha256`, `Registry`, `DocumentType`, `SourceDocument`, and `DocumentVersion` for schema export and later ingestion code.

- [x] **Step 1: Write document-model tests**

Create `tests/unit/domain/test_documents.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

import catchain.domain as domain


def test_source_document_accepts_traceable_identity() -> None:
    document = domain.SourceDocument(
        registry=domain.Registry.VERRA,
        registry_project_id="VCS-1234",
        source_url="https://registry.example/projects/1234/pdd.pdf",
        document_type=domain.DocumentType.PROJECT_DESCRIPTION,
        title="Project design document",
        discovered_at=datetime(2026, 9, 9, 8, 0, tzinfo=UTC),
    )

    assert document.registry is domain.Registry.VERRA
    assert document.registry_project_id == "VCS-1234"
    assert str(document.source_url).startswith("https://")


def test_source_document_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        domain.SourceDocument(
            registry=domain.Registry.ACR,
            registry_project_id="ACR-1",
            source_url="https://registry.example/acr-1.pdf",
            document_type=domain.DocumentType.OTHER,
            discovered_at=datetime(2026, 9, 9, tzinfo=UTC),
            invented_field="not allowed",
        )


def test_document_version_rejects_uppercase_sha256() -> None:
    with pytest.raises(ValidationError):
        domain.DocumentVersion(
            source_document_id=uuid4(),
            sha256="A" * 64,
            retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
            content_type="application/pdf",
            file_name="pdd.pdf",
            byte_size=42,
        )


def test_document_version_rejects_non_positive_size() -> None:
    with pytest.raises(ValidationError):
        domain.DocumentVersion(
            source_document_id=uuid4(),
            sha256="a" * 64,
            retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
            content_type="application/pdf",
            file_name="pdd.pdf",
            byte_size=0,
        )


def test_document_version_is_immutable() -> None:
    version = domain.DocumentVersion(
        source_document_id=uuid4(),
        sha256="a" * 64,
        retrieved_at=datetime(2026, 9, 9, tzinfo=UTC),
        content_type="application/pdf",
        file_name="pdd.pdf",
        byte_size=42,
    )

    with pytest.raises(ValidationError, match="frozen_instance"):
        version.byte_size = 84
```

- [x] **Step 2: Run the tests and verify the expected import failure**

Run:

```bash
uv run pytest tests/unit/domain/test_documents.py -v
```

Expected: five tests FAIL because the public document models do not exist.

- [x] **Step 3: Define common domain constraints**

Create `src/catchain/domain/common.py`:

```python
"""Constraints shared by CATchain domain models."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ImmutableDomainModel(BaseModel):
    """Base class for validated immutable domain values."""

    model_config = ConfigDict(extra="forbid", frozen=True)
```

- [x] **Step 4: Implement the document models**

Create `src/catchain/domain/documents.py`:

```python
"""Document discovery and content-version models."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, HttpUrl

from catchain.domain.common import ImmutableDomainModel, Sha256


class Registry(StrEnum):
    ACR = "acr"
    GOLD_STANDARD = "gold_standard"
    VERRA = "verra"


class DocumentType(StrEnum):
    PROJECT_DESCRIPTION = "project_description"
    MONITORING_REPORT = "monitoring_report"
    VALIDATION_REPORT = "validation_report"
    VERIFICATION_REPORT = "verification_report"
    REGISTRY_EXPORT = "registry_export"
    OTHER = "other"


class SourceDocument(ImmutableDomainModel):
    source_document_id: UUID = Field(default_factory=uuid4)
    registry: Registry
    registry_project_id: str = Field(min_length=1)
    source_url: HttpUrl
    document_type: DocumentType
    title: str | None = None
    discovered_at: AwareDatetime


class DocumentVersion(ImmutableDomainModel):
    document_version_id: UUID = Field(default_factory=uuid4)
    source_document_id: UUID
    sha256: Sha256
    retrieved_at: AwareDatetime
    content_type: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    byte_size: int = Field(gt=0)
    declared_version: str | None = None
```

- [x] **Step 5: Publish the document-model API**

Replace `src/catchain/domain/__init__.py` with:

```python
"""Public domain models for CATchain."""

from catchain.domain.common import Sha256
from catchain.domain.documents import DocumentType, DocumentVersion, Registry, SourceDocument

__all__ = [
    "DocumentType",
    "DocumentVersion",
    "Registry",
    "Sha256",
    "SourceDocument",
]
```

- [x] **Step 6: Run tests and static checks**

Run:

```bash
uv run pytest tests/unit/domain/test_documents.py -v
uv run ruff check src/catchain/domain tests/unit/domain/test_documents.py
```

Expected: both commands PASS.

- [x] **Step 7: Commit the document contracts**

```bash
git add src/catchain/domain tests/unit/domain/test_documents.py
git commit -m "feat: model source documents and versions"
```

---

### Task 3: Model Evidence and Pipeline Lifecycle

**Files:**

- Create: `src/catchain/domain/evidence.py`
- Create: `src/catchain/domain/pipeline.py`
- Modify: `src/catchain/domain/__init__.py`
- Test: `tests/unit/domain/test_evidence.py`
- Test: `tests/unit/domain/test_pipeline.py`

**Interfaces:**

- Consumes: `ImmutableDomainModel` and `Sha256` from Task 2.
- Produces: `EvidenceRef`, `PipelineStage`, `RunStatus`, and `PipelineRun` for extractors, validators, and orchestration in later slices.

- [x] **Step 1: Write evidence-model tests**

Create `tests/unit/domain/test_evidence.py`:

```python
from uuid import uuid4

import pytest
from pydantic import ValidationError

import catchain.domain as domain


def test_evidence_uses_one_based_page_and_optional_offsets() -> None:
    evidence = domain.EvidenceRef(
        document_version_id=uuid4(),
        page_number=18,
        quote="Expected annual emission reductions are 120,000 tCO2e.",
        char_start=240,
        char_end=296,
    )

    assert evidence.page_number == 18
    assert evidence.char_end > evidence.char_start


@pytest.mark.parametrize(
    ("char_start", "char_end"),
    [(10, None), (None, 20), (20, 20), (21, 20)],
)
def test_evidence_rejects_incomplete_or_reversed_offsets(
    char_start: int | None,
    char_end: int | None,
) -> None:
    with pytest.raises(ValidationError):
        domain.EvidenceRef(
            document_version_id=uuid4(),
            page_number=1,
            quote="Source text",
            char_start=char_start,
            char_end=char_end,
        )


def test_evidence_rejects_zero_based_page() -> None:
    with pytest.raises(ValidationError):
        domain.EvidenceRef(
            document_version_id=uuid4(),
            page_number=0,
            quote="Source text",
        )
```

- [x] **Step 2: Write pipeline-run tests**

Create `tests/unit/domain/test_pipeline.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

import catchain.domain as domain

STARTED = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)


def test_succeeded_pipeline_run_has_finish_time_and_no_error() -> None:
    run = domain.PipelineRun(
        stage=domain.PipelineStage.HASHED,
        status=domain.RunStatus.SUCCEEDED,
        input_hash="a" * 64,
        config_hash="b" * 64,
        started_at=STARTED,
        finished_at=STARTED + timedelta(seconds=2),
    )

    assert run.status is domain.RunStatus.SUCCEEDED
    assert run.error_code is None


def test_failed_pipeline_run_requires_typed_error() -> None:
    with pytest.raises(ValidationError, match="failed run requires"):
        domain.PipelineRun(
            stage=domain.PipelineStage.PARSED,
            status=domain.RunStatus.FAILED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED + timedelta(seconds=1),
        )


def test_pipeline_run_rejects_finish_before_start() -> None:
    with pytest.raises(ValidationError, match="before started_at"):
        domain.PipelineRun(
            stage=domain.PipelineStage.DOWNLOADED,
            status=domain.RunStatus.SUCCEEDED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED - timedelta(seconds=1),
        )


def test_running_pipeline_run_rejects_finish_time() -> None:
    with pytest.raises(ValidationError, match="running run cannot have finished_at"):
        domain.PipelineRun(
            stage=domain.PipelineStage.DOWNLOADED,
            status=domain.RunStatus.RUNNING,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED + timedelta(seconds=1),
        )


def test_completed_pipeline_run_requires_finish_time() -> None:
    with pytest.raises(ValidationError, match="completed run requires finished_at"):
        domain.PipelineRun(
            stage=domain.PipelineStage.HASHED,
            status=domain.RunStatus.SUCCEEDED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
        )


def test_succeeded_pipeline_run_rejects_error_details() -> None:
    with pytest.raises(ValidationError, match="only failed run may contain error details"):
        domain.PipelineRun(
            stage=domain.PipelineStage.HASHED,
            status=domain.RunStatus.SUCCEEDED,
            input_hash="a" * 64,
            config_hash="b" * 64,
            started_at=STARTED,
            finished_at=STARTED + timedelta(seconds=1),
            error_code="UNEXPECTED",
            error_message="This run should not carry errors.",
        )
```

- [x] **Step 3: Run both test modules and verify import failures**

Run:

```bash
uv run pytest tests/unit/domain/test_evidence.py tests/unit/domain/test_pipeline.py -v
```

Expected: nine tests FAIL because the public evidence and pipeline models do not exist.

- [x] **Step 4: Implement `EvidenceRef` invariants**

Create `src/catchain/domain/evidence.py`:

```python
"""References from extracted facts back to source text."""

from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from catchain.domain.common import ImmutableDomainModel


class EvidenceRef(ImmutableDomainModel):
    document_version_id: UUID
    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be provided together")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end <= self.char_start
        ):
            raise ValueError("char_end must be greater than char_start")
        return self
```

- [x] **Step 5: Implement pipeline lifecycle invariants**

Create `src/catchain/domain/pipeline.py`:

```python
"""Pipeline stage and execution-state models."""

from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from catchain.domain.common import ImmutableDomainModel, Sha256


class PipelineStage(StrEnum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    HASHED = "hashed"
    PARSED = "parsed"
    OCR_REQUIRED = "ocr_required"
    OCR_PARSED = "ocr_parsed"
    BASELINE_EXTRACTED = "baseline_extracted"
    LLM_EXTRACTED = "llm_extracted"
    SCHEMA_VALIDATED = "schema_validated"
    QUALITY_VALIDATED = "quality_validated"
    CANONICALIZED = "canonicalized"
    SCORED = "scored"
    EVALUATED = "evaluated"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineRun(ImmutableDomainModel):
    pipeline_run_id: UUID = Field(default_factory=uuid4)
    stage: PipelineStage
    status: RunStatus
    input_hash: Sha256
    config_hash: Sha256
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at cannot be before started_at")
        if self.status is RunStatus.RUNNING and self.finished_at is not None:
            raise ValueError("running run cannot have finished_at")
        if self.status is not RunStatus.RUNNING and self.finished_at is None:
            raise ValueError("completed run requires finished_at")
        if self.status is RunStatus.FAILED:
            if not self.error_code or not self.error_message:
                raise ValueError("failed run requires error_code and error_message")
        elif self.error_code is not None or self.error_message is not None:
            raise ValueError("only failed run may contain error details")
        return self
```

- [x] **Step 6: Export the new public types**

Replace `src/catchain/domain/__init__.py` with:

```python
"""Public domain models for CATchain."""

from catchain.domain.common import Sha256
from catchain.domain.documents import DocumentType, DocumentVersion, Registry, SourceDocument
from catchain.domain.evidence import EvidenceRef
from catchain.domain.pipeline import PipelineRun, PipelineStage, RunStatus

__all__ = [
    "DocumentType",
    "DocumentVersion",
    "EvidenceRef",
    "PipelineRun",
    "PipelineStage",
    "Registry",
    "RunStatus",
    "Sha256",
    "SourceDocument",
]
```

- [x] **Step 7: Run tests and static checks**

Run:

```bash
uv run pytest tests/unit/domain -v
uv run ruff check src/catchain/domain tests/unit/domain
```

Expected: all tests PASS and Ruff reports no errors.

- [x] **Step 8: Commit evidence and lifecycle models**

```bash
git add src/catchain/domain tests/unit/domain/test_evidence.py \
  tests/unit/domain/test_pipeline.py
git commit -m "feat: model evidence and pipeline lifecycle"
```

---

### Task 4: Export Deterministic JSON Schemas

**Files:**

- Create: `src/catchain/schema_export.py`
- Create: `src/catchain/cli.py`
- Test: `tests/unit/test_schema_export.py`
- Generate: `schemas/generated/source-document.schema.json`
- Generate: `schemas/generated/document-version.schema.json`
- Generate: `schemas/generated/evidence-ref.schema.json`
- Generate: `schemas/generated/pipeline-run.schema.json`

**Interfaces:**

- Consumes: `SourceDocument`, `DocumentVersion`, `EvidenceRef`, and `PipelineRun` from Tasks 2 and 3.
- Produces: `generate_json_schemas(output_dir: Path) -> list[Path]` and CLI command `catchain schema export --output-dir PATH`.

- [x] **Step 1: Write schema-export tests**

Create `tests/unit/test_schema_export.py`:

```python
import json
from pathlib import Path
from typing import Annotated

from typer.testing import CliRunner


def test_generate_json_schemas_exports_public_models(tmp_path: Path) -> None:
    from catchain.schema_export import generate_json_schemas

    written = generate_json_schemas(tmp_path)

    assert [path.name for path in written] == [
        "document-version.schema.json",
        "evidence-ref.schema.json",
        "pipeline-run.schema.json",
        "source-document.schema.json",
    ]
    source_schema = json.loads(
        (tmp_path / "source-document.schema.json").read_text(encoding="utf-8")
    )
    assert source_schema["title"] == "SourceDocument"
    assert source_schema["additionalProperties"] is False
    assert "registry_project_id" in source_schema["properties"]


def test_generate_json_schemas_is_deterministic(tmp_path: Path) -> None:
    from catchain.schema_export import generate_json_schemas

    first_paths = generate_json_schemas(tmp_path)
    first_contents = {path.name: path.read_bytes() for path in first_paths}

    second_paths = generate_json_schemas(tmp_path)
    second_contents = {path.name: path.read_bytes() for path in second_paths}

    assert second_contents == first_contents


def test_schema_export_cli_reports_written_files(tmp_path: Path) -> None:
    from catchain.cli import app

    runner = CliRunner()

    result = runner.invoke(app, ["schema", "export", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Exported 4 schemas" in result.stdout
```

- [x] **Step 2: Run tests and verify the expected import failure**

Run:

```bash
uv run pytest tests/unit/test_schema_export.py -v
```

Expected: three tests FAIL because `catchain.cli` and `catchain.schema_export` do not exist.

- [x] **Step 3: Implement deterministic schema generation**

Create `src/catchain/schema_export.py`:

```python
"""Generate version-controlled JSON Schemas from CATchain domain models."""

import json
from pathlib import Path
from typing import type

from pydantic import BaseModel

from catchain.domain import DocumentVersion, EvidenceRef, PipelineRun, SourceDocument

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "document-version": DocumentVersion,
    "evidence-ref": EvidenceRef,
    "pipeline-run": PipelineRun,
    "source-document": SourceDocument,
}


def generate_json_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for schema_name, model_type in sorted(SCHEMA_MODELS.items()):
        output_path = output_dir / f"{schema_name}.schema.json"
        serialized = json.dumps(
            model_type.model_json_schema(),
            indent=2,
            sort_keys=True,
        )
        output_path.write_text(f"{serialized}\n", encoding="utf-8")
        written.append(output_path)

    return written
```

- [x] **Step 4: Implement the CLI command**

Create `src/catchain/cli.py`:

```python
"""CATchain command-line interface."""

from pathlib import Path

import typer

from catchain.schema_export import generate_json_schemas

app = typer.Typer(help="Traceable carbon document processing.")
schema_app = typer.Typer(help="Manage generated schemas.")
app.add_typer(schema_app, name="schema")


@schema_app.command("export")
def export_schemas(
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("schemas/generated"),
) -> None:
    written = generate_json_schemas(output_dir)
    typer.echo(f"Exported {len(written)} schemas to {output_dir}")
```

- [x] **Step 5: Run the focused tests**

Run:

```bash
uv run pytest tests/unit/test_schema_export.py -v
```

Expected: all three tests PASS.

- [x] **Step 6: Generate the committed schemas and verify clean regeneration**

Run:

```bash
uv run catchain schema export --output-dir schemas/generated
git diff -- schemas/generated
uv run catchain schema export --output-dir schemas/generated
git diff --exit-code -- schemas/generated
```

Expected: four schema files are created by the first command; the second generation introduces no additional diff.

- [x] **Step 7: Run all tests and static checks**

Run:

```bash
uv run pytest -v
uv run ruff check .
```

Expected: all tests PASS and Ruff reports no errors.

- [x] **Step 8: Commit schema generation**

```bash
git add src/catchain/cli.py src/catchain/schema_export.py \
  tests/unit/test_schema_export.py schemas/generated
git commit -m "feat: export domain JSON schemas"
```

---

### Task 5: Add the First Project-linked Learning Note

**Files:**

- Create: `docs/learning/01-domain-model-schema-validation.md`
- Modify: `README.md`

**Interfaces:**

- Consumes: the implemented models, tests, and generated schemas from Tasks 1-4.
- Produces: a learning artifact that explains the exact code and a README link that makes the lesson discoverable.

- [x] **Step 1: Write the learning note**

Create `docs/learning/01-domain-model-schema-validation.md` with this content:

````markdown
# Lesson 1: Domain Models, Schema, and Validation

## The problem this slice solves

Before CATchain downloads or asks an LLM to interpret a document, it needs explicit
contracts for document identity, content versions, evidence, and pipeline execution.
Without those contracts, later code can produce dictionaries with missing fields,
wrong types, ambiguous page numbers, or error states that cannot be audited.

## 1. What is a domain model?

A domain model is a code representation of a business concept. `SourceDocument` means
the logical document discovered at a registry URL. `DocumentVersion` means the exact
bytes retrieved at one time, identified by SHA-256. Separating them allows one source
document to have multiple content versions.

## 2. Plain-language analogy

`SourceDocument` is the book title in a library catalogue. `DocumentVersion` is one
specific edition whose pages and contents can differ. SHA-256 is the edition's digital
fingerprint.

## 3. Why CATchain needs these models

Carbon project documents are updated. A score based on an old PDD must not be presented
as if it came from the newest PDD. The source/version split makes that distinction
queryable and testable.

## 4. Which code implements the concept?

- `src/catchain/domain/documents.py` defines source and version identity.
- `src/catchain/domain/evidence.py` links a future extracted fact to a document version
  and one-based page.
- `src/catchain/domain/pipeline.py` records what stage ran and whether it succeeded.
- `src/catchain/schema_export.py` derives portable JSON Schema from those models.

## 5. Inputs

The models accept typed Python values such as registry name, project identifier, URL,
retrieval time, SHA-256, content size, page number, quote, stage, and run status.

## 6. Outputs

A valid input produces an immutable Pydantic object. Invalid input produces a structured
`ValidationError`. Schema export produces deterministic `.schema.json` files.

## 7. Underlying principle

Pydantic reads Python type annotations and field constraints, validates input at runtime,
and represents the same constraints in JSON Schema. `extra="forbid"` rejects unknown
fields. `frozen=True` prevents accidental mutation after construction.

## 8. Why not use dictionaries?

A dictionary permits misspelled keys, unexpected values, and silent shape changes. Typed
models move these failures to the boundary where they can be handled deliberately. A
database alone is also insufficient because data must be validated before persistence
and passed safely between pipeline stages.

## 9. Interview questions

- Why distinguish a logical source document from a content version?
- What can JSON Schema validate, and what can it not prove?
- Why is structured output not the same as factual correctness?
- What is the difference between validation and normalization?
- Why reject unknown fields?

## 10. Minimum explanation you should be able to give

"CATchain uses immutable Pydantic domain models as the source of truth. A source document
represents registry identity, while a document version represents exact retrieved bytes
identified by SHA-256. Evidence points to a specific version and page. Pydantic rejects
structurally invalid values and generates JSON Schema, but it cannot prove that an LLM's
claim is supported by a document; evidence validation is a separate later stage."

## Input/output walkthrough

```python
version = DocumentVersion(
    source_document_id=source_id,
    sha256="a" * 64,
    retrieved_at=retrieved_at,
    content_type="application/pdf",
    file_name="pdd.pdf",
    byte_size=2048,
)
```

Input: identity, checksum, timestamp, media information, and byte size.

Output: an immutable validated `DocumentVersion` whose data can be serialized, stored,
or referenced by `EvidenceRef`.

If `sha256` is malformed, `byte_size` is zero, the timestamp lacks a timezone, or an
unknown field is supplied, construction fails. Removing these constraints would allow
ambiguous or non-reproducible records into every later CATchain stage.

## Self-check

1. Explain why URL alone cannot identify the exact document used for a score.
2. Explain why a valid JSON object can still contain a hallucinated value.
3. Explain why CATchain uses one-based page numbers in external evidence.
4. Point to the test that prevents uppercase or malformed SHA-256 values.
5. Describe what deleting `extra="forbid"` would change.
````

- [x] **Step 2: Link the lesson from the README**

Append to `README.md`:

```markdown
## Learning path

- [Lesson 1: Domain Models, Schema, and Validation](docs/learning/01-domain-model-schema-validation.md)
```

- [x] **Step 3: Verify documentation references and the complete slice**

Run:

```bash
test -f docs/learning/01-domain-model-schema-validation.md
uv run pytest -v
uv run ruff check .
git diff --check
```

Expected: the learning file exists, all tests pass, Ruff passes, and `git diff --check` produces no output. The prose itself is reviewed by a person rather than treated as code behavior.

- [x] **Step 4: Commit the learning artifact**

```bash
git add README.md docs/learning/01-domain-model-schema-validation.md
git commit -m "docs: teach domain models and schema validation"
```

---

## Slice 1 Final Verification

Run:

```bash
uv sync --dev
uv run pytest -v
uv run ruff check .
uv run catchain schema export --output-dir schemas/generated
git diff --exit-code
git status --short
```

Expected:

- All tests pass.
- Ruff reports no errors.
- Schema regeneration changes no committed file.
- Git diff is empty.
- Git status is empty.

Inspect the package boundary:

```bash
uv run python -c "from catchain.domain import DocumentVersion, EvidenceRef; print(DocumentVersion.__name__, EvidenceRef.__name__)"
```

Expected:

```text
DocumentVersion EvidenceRef
```

The learner checkpoint is complete when the project owner can explain:

1. Why `SourceDocument` and `DocumentVersion` are separate.
2. Why SHA-256 is an identity mechanism rather than a quality score.
3. What Pydantic validates at runtime.
4. What JSON Schema can and cannot establish.
5. Why evidence points to a particular document version and page.
6. Why pipeline failure is structured data rather than an empty string.
