# Slice 4 Business Fields Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task in the existing isolated worktree.

**Goal:** Migrate explicit project-title, company-role and crediting-period candidates with page evidence.
**Architecture:** Extend the shared scalar observation contract and existing regex matcher. Keep repeated roles as separate observations; a label containing multiple companies remains one raw candidate pending entity resolution. Never infer company roles from generic known-organization mentions.
**Tech Stack:** Existing Python/Pydantic/re/pytest/Ruff; no dependencies.
**Spec:** `docs/superpowers/specs/2026-09-09-catchain-redesign.md`, plus `docs/audit/2026-09-17-final-delivery-reconciliation.md`.

## Decisions

- Add project_participant, project_owner, project_developer, project_operator,
  crediting_period_years, crediting_period_start and crediting_period_end to FieldName.
- Reuse project_name for explicit title labels. Country remains country, not a full location/address. Location and general company detection are still scope gaps.
- Dates remain strings, marked date_not_validated; a bare year adds year_only_date and numeric slash dates add ambiguous_numeric_date. Never invent month/day or label them validated.
- Add validation_status with only unvalidated permitted in the extraction contract. Validators produce their own results in Slice 6.
- Schema 1.1.0 requires pipeline_run_id supplied by the caller. Keep 1.0.0 reading support for old artifacts with no run ID; no synthetic run is invented on reading. Persistent run existence is checked at the future persistence boundary.
- Extractor version teacher-final-page-regex-v2. Known-organization scan, primary company ranking, contact extraction and automatic company splitting are not claimed as migrated.

## Task 1: Contract and matcher

Files: `domain/extraction.py`, `extraction/baseline/regex.py`, their existing tests and generated schemas.

- [x] Write one two-page title/role/date test; assert raw 03/04/2020 survives, year 2027 stays a year, two owner candidates survive and a generic SGS mention does not become verifier.
- [x] Run test and confirm failure before implementation.
- [x] Add Literal fields, schema compatibility and processing-run validation. Extend RULES with anchored line labels and original crediting regex; normalize spaces after computing evidence offsets, preserve raw values. Avoid splitting on and or slash within legal names.
- [x] Run `venv/bin/python -m pytest -q`, Ruff and schema regeneration check. Compare synthetic title/crediting values with final-delivery functions.
- [x] Run existing 11-PDF native-text development pilot, save private output separately from v1; verify all evidence slices. Record field match counts as coverage observations, not accuracy.
- [x] Update inventory, learning and progress; commit only related files.

Example check: `assert start.raw_value == "03/04/2020" and "ambiguous_numeric_date" in start.issues`.

## Remaining Task 2B checkpoint

Historical registry URL/collector audit, broader company entity resolution and source-run persistence remain open. Do not mark the entire Task 2B or Slice 4 complete from this narrower delivery.
