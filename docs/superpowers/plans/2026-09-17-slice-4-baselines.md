# Slice 4 Extraction and Keyword Baselines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce evidence-backed regex candidates in a shared extraction contract and reproduce the teacher-final 12-dimension keyword baseline separately.

**Architecture:** Reuse immutable Pydantic models, EvidenceRef, ParsedDocument and schema export. Match original page text; maintain multiple candidates without canonicalizing. Store derived JSON through the existing CLI pattern; keyword scoring consumes Parsed text independently of extraction.

**Tech Stack:** Python 3.12+, Pydantic 2, standard-library re/json/hashlib, existing Typer/pytest/Ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-09-catchain-redesign.md`

## Global Constraints

- Raw inputs are immutable.
- Every material fact is traceable.
- Regex and LLM extraction share one output contract.
- Extraction and scoring are separate.
- Data quality and project quality are separate.
- Abstention is a valid result.
- Prompts, schemas, parsers, and rubrics are versioned.
- Large source documents, runtime databases, credentials, and private data are excluded from version control.
- No new production dependencies, LLM invocation, canonical writes or review console in this slice.
- Audit reference: `docs/audit/2026-09-17-slice-4-baseline-audit.md`.
- Runtime page offsets are page-local, matching ParsedPage. Slice 3's plan says combined-text offsets; that wording must be corrected, not copied into runtime behavior.

## Task 1: Shared extraction contract

**Files:** Create `src/catchain/domain/extraction.py`, `tests/unit/domain/test_extraction.py`; modify `domain/__init__.py`, `schema_export.py`; generate `schemas/generated/field-observation.schema.json` and `project-extraction.schema.json`.

**Interfaces:** `FieldObservation` carries field_name, raw_value, normalized_value, unit, confidence, evidence, missing_reason, issues. `ProjectExtraction` carries project_id, registry, document_version_id, parsed_document_id, extractor_name, extractor_version, schema_version, created_at, observations. Reuse Registry, AwareDatetime and EvidenceRef.

- [x] Write focused round-trip and invalid-candidate tests. Instantiate a capacity candidate with value 12.5, quote `12.5 MW`, page 1, offsets 0–7; serialize/validate; reject a value lacking evidence and a missing observation carrying a value.
- [x] Run `venv/bin/python -m pytest tests/unit/domain/test_extraction.py -q`; confirm new model import fails before implementation.
- [x] Implement immutable models. Field names are a Literal union of the 47 inventory names plus `country`; project_id and registry also exist in the envelope. Normalized scalar uses strict str/int/float/bool, preventing coercion of false to zero. Dates stay raw strings for Slice 6 validation. Missing reasons are `not_found`, `unsupported_by_baseline`, `ambiguous`. Value candidates need nonempty raw_value and evidence; missing entries need a reason and null values. Confidence is optional [0,1]; regex supplies None. Multiple observations of the same field are permitted; no last-write-wins.
- [x] Validate envelope evidence version matches document_version_id. Reject empty project identity/version strings. Default schema_version `1.0.0`; candidates remain unvalidated, with issues as immutable strings. Do not add reviewer or audit-history objects before Slice 8.
- [x] Export both schemas via SCHEMA_MODELS; run domain tests and `tests/unit/test_schema_export.py` if present, otherwise locate the existing schema tests using `rg --files tests`. Verify re-export is byte-stable.
- [x] Commit only contract files and generated schemas: `feat: define evidence-backed extraction contracts`.

Example contract behavior to test:

```python
observation = FieldObservation(
    field_name="installed_capacity_mw", raw_value="12.5",
    normalized_value=12.5, unit="MW", evidence=(evidence,),
)
assert FieldObservation.model_validate_json(observation.model_dump_json()) == observation
```

## Task 2: Page-based regex baseline

**Files:** Create `src/catchain/extraction/baseline/regex.py`, package `__init__.py` files, `tests/unit/extraction/test_regex.py`.

**Interfaces:** `extract_regex(parsed: ParsedDocument, project_id: str, registry: Registry) -> ProjectExtraction`. Extractor version `teacher-final-page-regex-v1`.

- [x] Write a generated two-page ParsedDocument test with `Host country: Brazil` and `Installed capacity: 12.5 MW`; assert country and capacity candidates, page-specific version/quote/offsets, and `not_found` for supported unmatched fields.
- [x] Run the test and confirm missing function failure.
- [x] Implement audited country/validator/verifier/methodology/grid/capacity/BE/PE/LE/ER rules. Reuse original regex patterns and cleanup order; clean captured values after matching, never alter text before computing offsets. Attach a page-local context quote around the match and exact char_start/char_end. Use `re.finditer` to keep different candidates and prevent repeated identical page spans. Raw capture remains unchanged; number normalization removes commas. Record `broad_numeric_rule` and `unit_not_verified` for emission amounts without explicit units. First-match selection exists only in comparison reports.
- [x] Emit one missing observation for each unsupported/unmatched inventory field. Context project_id is not evidence of the document's project name. Country is an additional field; registry stays source context. Do not convert keyword absence to false or map arbitrary years to EF years.
- [x] Run one multi-candidate/evidence check: `assert page.text[e.char_start:e.char_end] == e.quote` for every emitted evidence, and verify conflicting numbers remain two candidates.
- [x] Run relevant tests, Ruff, and commit `feat: migrate page-based regex extraction baseline`.

## Task 2B: Reconcile and migrate the final delivery business assets

Added on 2026-09-17 from the explicit primary delivery path. Read
`docs/audit/2026-09-17-final-delivery-reconciliation.md` first. Task 2 is only the
initial scalar baseline, not a full migration of that delivery.

**Files:** Modify `src/catchain/domain/extraction.py`, generated schemas,
`src/catchain/extraction/baseline/regex.py`, `tests/unit/extraction/test_regex.py`,
`docs/product/ACM0002_EXTRACTION_FIELD_INVENTORY.md` and this plan.

- [x] Reconcile final-delivery company_info, project title, host country and
crediting-period output with the existing 47 assessment-input fields. Record
field types, roles and evidence representation; do not collapse companies into
an unspecified single company value or turn year-only dates into exact dates.
- [x] Define a separate incremental implementation plan for these confirmed
assets before changing the contract. Add processing-run linkage and explicit
validation state before extraction persistence/LLM integration.
- [ ] Implement the confirmed title/company/crediting rules with one focused
candidate/evidence check and versioned extractor/schema outputs. Preserve raw
ambiguous dates, company roles, multiple candidates and missing reasons.
- [x] Compare with final-delivery synthetic and real development outputs;
record intentional cleaning and matching differences rather than claiming parity.
- [x] Audit historical registry collectors and actual URL/download calls; record
confirmed rules and unverified URLs in the ingestion backlog. No network sync is
scheduled until retry and dedup behavior has a runnable check.

**2026-09-17 checkpoint:** Explicit title/company-role/crediting rules are implemented,
old assets and registry URL calls are audited. Full company entity resolution is
not implemented; its unchecked migration step remains an explicit backlog rather
than blocking independent keyword-baseline preservation. See
`docs/audit/2026-09-17-registry-collectors-company-assets.md` for the evidence and limits.

## Task 3: Independent keyword baseline

**Files:** Create `src/catchain/scoring/teacher-final-keywords-v1.json`, `src/catchain/scoring/keyword_baseline.py`, `tests/unit/scoring/test_keyword_baseline.py`.

**Interfaces:** `score_keywords(parsed_documents: tuple[ParsedDocument, ...]) -> dict`. Return baseline_version, dimensions, total_score, max_score=36, keyword_score_ratio; each dimension includes score, high/mid counts and up to three EvidenceRef entries serialized with model_dump(mode="json"). Empty document tuple is rejected.

- [x] Copy the audited DIMENSION_RULES data into JSON using `runpy.run_path` only during migration. Record source hash in config; never import the old package at runtime.
- [x] Write threshold and denial counterexample test; confirm missing function failure. Test scores 0/1/2/3 with artificial high/mid patterns and assert the audited D01 denial still scores 3 as a documented baseline limitation.
- [x] Load one installed config file relative to package/repository conventions; no generic scoring factory. Count presence per pattern across all pages/documents with re.I. Keep first page match evidence for each matched pattern, high before mid. Cross-page regex matches are intentionally unsupported; record this difference in comparison output. Apply exact audited thresholds.
- [x] Compare migrated counts/scores against old score_dimension for page-contained synthetic texts across all 12 dimensions; assert equal. Verify repeated keywords do not increase a pattern's count. The dict output is explicitly baseline data, not AssessmentResult or CanonicalProject.
- [x] Run scoring test, Ruff; commit `feat: preserve versioned teacher-final keyword baseline`.

**Packaging decision:** Keep the single rule JSON inside catchain.scoring and
load with importlib.resources, so the wheel works outside the source checkout.
No duplicate configs copy or new loader framework. Wheel resource access was
verified from /tmp. Input document identities and rules hash are included;
processing-run persistence is added at the CLI boundary in Task 4.

## Task 4: CLI, real output and learning checkpoint

**Files:** Modify `src/catchain/cli.py`, `README.md`, `docs/PROJECT_PROGRESS.md`; create `tests/integration/test_cli_extraction.py`, `docs/validation/2026-09-17-slice-4-baselines.md`, `docs/learning/04-extraction-keyword-baselines.md`.

**Interfaces:** `catchain extract baseline PARSED_ID --project-id ID --registry REGISTRY --database PATH --output-dir PATH`; `catchain score keywords PARSED_ID --database PATH --output-dir PATH`. Add `DocumentRepository.get_parsed(parsed_document_id: UUID) -> ParsedDocument | None` in `document_repository.py`, sharing reconstruction with existing find_parsed instead of duplicating it.

- [x] Write integration test ingest→parse→extract→score using generated non-private PDF and temporary database/output. Unknown Parsed ID returns structured failure and Exit 1; no output is written on failure.
- [x] Run test before implementing commands. Wire exact functions from Tasks 2–3. Return artifact_path, identity, matched/missing field counts and baseline versions in JSON. Derived filenames use SHA256 of deterministic JSON content excluding created_at; include Parsed ID, extractor/schema/rule versions. Repeated input reuses the existing file and does not overwrite it; reject differing content under the same key.
- [x] Run full `venv/bin/python -m pytest -q` and `venv/bin/ruff check .`; verify all schemas regenerate identically. No new test framework or duplicate parsing pipeline.
- [x] On the existing 11-document development pilot, read source PDFs without changing them; reuse/import Parsed artifacts as needed. Save private output in ignored `data/extracted/`. Verify every candidate quote against its page. Report matched-field coverage, missing counts, conflict counts and evidence integrity separately from keyword_score_ratio. Do not claim accuracy without human labels. Record GS shortfall and OCR tool availability.
- [x] Compare first-match compatible fields and per-dimension keyword scores with the legacy code using the same native page text. Explain page boundary, missing-as-null and normalized-name differences; preserve legacy extras in ignored comparison JSON.
- [x] Write lesson using one actual output: regex candidate→source quote→missing reason→keyword score. Update progress with completed tasks and exact next Slice; keep every prior product decision in the tracker. Record the owner explanation checkpoint after concrete results; avoid interrupting development with a quiz.
- [x] Commit `feat: expose and validate extraction and keyword baselines`.

**Implemented boundary:** Add src/catchain/storage/baseline_artifacts.py for one
atomic result/run bundle; no new database tables or dependencies. Persistent
failure runs and normalized facts/evidence tables remain later-slice work.
Three source URLs are explicit development placeholders, OCR is unavailable,
and the real-data run used native-text comparison settings. These limitations
are recorded rather than counted as production acceptance.

## Review checkpoint

The audit/planning checkpoint is complete when source hashes, actual fields and denial counterexample are recorded. Slice 4 itself is complete only after all four tasks and real-output checks pass. Human-review UI, confidence calibration, date authority, final rubric and gold-label metrics remain in Slices 6–8, with their earlier requirements preserved.
