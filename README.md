# CATchain

CATchain is a traceable carbon data engineering and AI structured-extraction system.
It preserves document identity and evidence before producing validated project records
and explainable assessments.

Slices 1 through 3 are complete: the system preserves immutable Raw versions,
extracts traceable per-page text, selectively routes meaningful low-quality pages
to OCR, and persists reproducible Parsed results. Slice 4 has completed its legacy
audit, shared extraction contract and initial page-based scalar regex baseline
(Tasks 1–2). Explicit title/company-role/crediting-period rules now emit schema
1.1.0 candidates with processing-run IDs. The independent, versioned 12-dimension
keyword baseline and CLI chain are implemented and compared with legacy outputs.
Broader company assets and network adapters remain pending. Slice 5 now includes a versioned prompt, a single-call DeepSeek JSON adapter,
response/run logging, grounding checks and the llm-once CLI. One real pilot call
has succeeded. Completed-input caching and opt-in pricing/budget controls are in place;
fixed-page Regex/LLM candidate comparison is available. Accuracy against human gold
labels remain pending. Slice 6 now includes mechanical candidate checks and explicit
human-review routing, conservative cross-field/version checks, and atomic SQLite
candidate/evidence imports. Explicit human review can now append grounded canonical
facts with immutable history and stale-write protection. No candidate is automatically
approved. Domain policy completeness and accuracy against human gold remain pending.
Slice 7 now audits approved facts against the legacy 12-dimension input catalog.
Readiness reports preserve provenance; scoring rules, weights and totals remain
unconfirmed. Readiness is not a project-quality score.
Optional human-attested assessment context now binds version and measurement periods
to exact approved facts. Business checks produce blocked reasons or a legacy ER
arithmetic diagnostic; official applicability, scoring rubrics and tolerances remain pending.
See [Project Progress](docs/PROJECT_PROGRESS.md) for the continuous implementation and
learning status.

中文入口：[使用说明](docs/USAGE_ZH.md) · [开发进度与后续计划](docs/PROJECT_PROGRESS.md)。
Maintainer: [cgzjiang-droid](https://github.com/cgzjiang-droid)。

## Development

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv sync --dev
uv run pytest
uv run ruff check .
uv run catchain schema export --output-dir schemas/generated
```

See `docs/superpowers/specs/2026-09-09-catchain-redesign.md` for the approved architecture.

## Import a local source document

```bash
uv run catchain ingest local ./project.pdf \
  --registry verra \
  --project-id VCS-1234 \
  --source-url https://registry.example/projects/1234/pdd.pdf \
  --document-type project_description
```

The command stores immutable bytes below `data/raw`, records source and version metadata in
`data/catchain.sqlite`, and reuses an existing version when the same content is imported again.
Use `--database` and `--raw-root` to select different runtime locations.

## Parse an imported Raw PDF

```bash
uv run catchain parse raw DOCUMENT_VERSION_UUID \
  --database data/catchain.sqlite \
  --raw-root data/raw
```

The command keeps good native PDF text, sends only meaningful low-quality pages to
Tesseract, records blank pages as warnings, and persists a reproducible Parsed result.
It returns JSON with the stored or reused status, configuration hash, page count, OCR
page count, and warnings. Use `--tesseract-executable` when Tesseract is installed at
a non-default path.

## Learning path

- [Lesson 1: Domain Models, Schema, and Validation](docs/learning/01-domain-model-schema-validation.md)
- [Lesson 2: Raw Ingestion, Hashing, and Versioning](docs/learning/02-raw-ingestion-versioning.md)
- [Lesson 3: PDF Parsing, Quality Routing, and OCR Fallback](docs/learning/03-pdf-parsing-ocr-fallback.md)
- [Lesson 4: Extraction and Keyword Baselines](docs/learning/04-extraction-keyword-baselines.md)
- [Lesson 5: LLM Extraction Boundaries](docs/learning/05-llm-extraction-boundary.md)
- [Hello-Agents chapter 1 learning lab](docs/learning/hello-agents/chapter-01-agent-basics.md)

## Baseline CLI chain

Use the Document version ID printed by ingest local, then the parsed_document_id
returned by parse raw. Project/registry must match the imported source.

```bash
venv/bin/catchain parse raw DOCUMENT_VERSION_UUID
venv/bin/catchain extract baseline PARSED_UUID --project-id PROJECT_ID --registry verra
venv/bin/catchain score keywords PARSED_UUID
```

All commands accept --database; baseline commands accept --output-dir. Extraction
and keyword results are separate immutable JSON bundles with their PipelineRun
records. Repeat inputs reuse the bundle; corrupted/conflicting bundles fail rather
than being overwritten. Candidate facts remain unvalidated. The SQLite document
and Parsed layers are implemented; canonical facts and assessment tables are not.
Keyword scores are comparison outputs, not verified project-quality scores.
