# CATchain Redesign Specification

**Status:** Approved design, pending implementation plan  
**Date:** 2026-09-09  
**Project:** CATchain  
**Primary objective:** Build a traceable carbon data engineering, AI structured extraction, data quality validation, and project assessment system while using the implementation as a practical AI engineering curriculum.

## 1. Context

The original CATchain was largely produced through natural-language instructions to coding agents. It demonstrated that a working prototype could be assembled, but it did not leave the project owner with a clear mental model of the code, AI boundaries, data lineage, or engineering decisions.

This redesign has two equally important outputs:

1. A more reliable and explainable CATchain product.
2. A learning path through which the project owner can explain the complete system from document ingestion to final assessment.

The product must not use AI terminology as decoration. A file named `agent`, `rag`, or `memory` is not evidence that the corresponding technique exists. Every capability must be established from its actual execution path, inputs, outputs, state transitions, and evaluation.

## 2. Legacy Audit Summary

The legacy implementation contains several distinct historical artifacts:

- A blockchain-oriented CATchain prototype containing React/Next, Express/Nest, Go, Hyperledger Fabric, PostgreSQL/QLDB/CouchDB, and IPFS components.
- A small deterministic JavaScript normalization step.
- A later ACM0002 delivery containing registry data processing, PDF parsing, regular-expression extraction, keyword scoring, JSONL/JSON/CSV/Excel outputs, and batch-processing scripts.

The ACM0002 delivery's real execution path was:

```text
Registry CSV
  -> requests / Playwright collection and document download
  -> PyMuPDF text extraction
  -> ACM0002 regular-expression filtering
  -> regular-expression field extraction
  -> keyword-presence scoring
  -> JSONL
  -> company-oriented JSON
  -> Excel
```

The audited legacy implementation did **not** contain real runtime use of Claude, GPT, structured LLM output, RAG, embeddings, a vector database, tool calling, or an agent loop. Its primary processing was deterministic Python and JavaScript.

Assets worth preserving are:

- Registry collection experience.
- ACM0002 project data.
- The existing field inventory.
- The business intent behind the 12-dimension scoring framework.
- Batch-processing experience.
- Existing regular expressions and keyword scoring as a measurable baseline.

Known weaknesses to address include:

- A keyword-score ratio mislabeled as coverage.
- Pre-filtering limited to a small number of candidate documents and pages.
- Keyword occurrence used as a proxy for project quality.
- No OCR fallback.
- Errors collapsed to empty values.
- A descriptive schema file that was not used for runtime validation.
- Duplicate scoring definitions in JSON and hard-coded Python.
- File-only outputs with no canonical database model.
- No field-level provenance, gold labels, or extraction evaluation.

The blockchain, token, matching, and legacy trading-interface modules remain historical prototypes and do not influence the new architecture.

## 3. Reference Project Findings

The `carbon-methodology-archive` repository is valuable primarily for its data-engineering discipline rather than as an implementation to copy. Relevant ideas include:

- File and document metadata.
- SHA-256 content identity.
- Source and version tracking.
- Clear raw and derived artifacts.
- Registry-specific collectors behind shared concepts.
- Tests around collection behavior.
- Reproducible change tracking.

The current public repository is largely data-oriented. Earlier history contained scraper infrastructure, tests, and a changelog generator that used an LLM only for summarizing deterministic changes. It is not evidence of an AI extraction or scoring architecture.

CATchain will adopt the useful provenance and data-lifecycle ideas, but will develop its own carbon-project schema, extraction, validation, scoring, and evaluation system.

`Hello-Agents` will be used as the learning sequence. Its concepts will be introduced when the project reaches the corresponding engineering need. Techniques such as RAG, memory, or multi-agent orchestration will not be forced into the production architecture merely to cover curriculum material.

## 4. Goals and Non-goals

### 4.1 Goals

- Import or collect international carbon project metadata and documents.
- Preserve immutable source documents with checksums and versions.
- Parse text with page-level provenance and OCR fallback.
- Extract project information into a shared schema using both a regex baseline and LLM structured extraction.
- Attach inspectable evidence to every material extracted fact.
- Validate structure, evidence, domain rules, and cross-document consistency.
- Produce a canonical project record without discarding candidates or conflicts.
- Preserve the legacy 12-dimension scoring system as a baseline.
- Build a versioned, evidence-based assessment system.
- Evaluate extraction, grounding, validation, scoring, agent behavior, product value, cost, and latency separately.
- Provide a human review workflow for uncertain or conflicting results.
- Add a genuine review agent only after stable tools and measured exception cases justify it.
- Teach the concepts exercised by each implementation slice.

### 4.2 Non-goals

- Hyperledger Fabric.
- Carbon tokens.
- Trading or order matching.
- Rebuilding the legacy carbon trading UI.
- Kubernetes or an early microservice architecture.
- A distributed task queue for the initial dataset.
- Mandatory RAG, embeddings, vector databases, LangGraph, multi-agent systems, memory, or fine-tuning.
- Allowing an LLM to write directly to canonical data or assign unexplained final scores.

## 5. Architectural Principles

1. **Raw inputs are immutable.** Corrections produce new metadata or versions rather than overwriting source evidence.
2. **Every material fact is traceable.** Evidence contains document identity, page, and quote.
3. **Probabilistic output is a candidate.** It becomes canonical only after validation and conflict resolution.
4. **Deterministic software remains deterministic.** Hashing, parsing mechanics, conversion, schema validation, persistence, and score aggregation use ordinary code.
5. **Regex and LLM extraction share one output contract.** This makes comparison meaningful.
6. **Extraction and scoring are separate.** A change in assessment policy does not require re-extracting documents.
7. **Data quality and project quality are separate.** Missing source material is not silently treated as poor project performance.
8. **Abstention is a valid result.** Insufficient evidence must not be converted into false certainty.
9. **Prompts, schemas, parsers, and rubrics are versioned.** Results must be reproducible and explainable.
10. **The initial system is a workflow.** Agent behavior is introduced only for decisions that cannot be specified efficiently as a fixed workflow.

## 6. System Architecture

```text
Registry metadata / project documents
                 |
                 v
       Ingestion, metadata, SHA-256
                 |
                 v
              Raw layer
                 |
                 v
      Text parsing and OCR fallback
                 |
                 v
             Parsed layer
                 |
          +------+------+
          |             |
          v             v
   Regex baseline   LLM extraction
          |             |
          +------+------+
                 v
            Extracted layer
                 |
                 v
      Schema, evidence, domain,
     and cross-document validation
                 |
                 v
          Canonical record
                 |
                 v
      Versioned 12D assessment
                 |
                 v
     Evaluation and review console
```

The batch workflow handles the standard path. Records with unresolved conflicts, invalid evidence, or insufficient information enter a review queue. A future review agent may investigate selected exceptions through constrained tools and must either resolve them with evidence or escalate to a person.

## 7. Data Layers and Domain Model

### 7.1 Raw

Raw stores source truth:

- Original bytes.
- Source URL and registry.
- Retrieval timestamp.
- HTTP metadata when available.
- SHA-256.
- Media type and filename.
- Registry project identifier.
- Document type and declared version when available.

Raw data is never silently rewritten.

### 7.2 Parsed

Parsed stores reproducible parser output:

- Per-page text.
- Page number and character offsets.
- Parser name and version.
- Text-quality measurements.
- OCR decision and OCR engine version.
- Parse warnings and errors.

Parsed artifacts can be regenerated from Raw without downloading the document again.

### 7.3 Extracted

Extracted stores extractor claims:

- Extractor type: regex or LLM.
- Extractor, prompt, model, and schema versions.
- Field values before canonicalization.
- Evidence references.
- Missing reasons.
- Confidence or abstention where meaningful.
- Validation outcomes.

### 7.4 Core Models

The initial domain model includes:

- `CarbonProject`
- `SourceDocument`
- `DocumentVersion`
- `ParsedDocument`
- `ExtractionRun`
- `FieldObservation`
- `EvidenceRef`
- `ValidationIssue`
- `CanonicalRecord`
- `ScoringRun`
- `PipelineRun`
- `LLMRun`

Pydantic models are the source of truth for runtime validation. JSON Schema is generated from those models rather than maintained as a second handwritten definition.

The storage layer uses a repository interface so that SQLite can later be replaced without changing domain and pipeline code.

## 8. Pipeline and Failure Semantics

The normal state sequence is:

```text
DISCOVERED
  -> DOWNLOADED
  -> HASHED
  -> PARSED | OCR_REQUIRED -> OCR_PARSED
  -> BASELINE_EXTRACTED
  -> LLM_EXTRACTED
  -> SCHEMA_VALIDATED
  -> QUALITY_VALIDATED
  -> CANONICALIZED
  -> SCORED
  -> EVALUATED
```

Each stage records:

- Input artifact identity.
- Configuration and code version.
- Start and end timestamps.
- Output artifact identity.
- Status, warnings, and typed failures.
- Retry count.

Idempotency keys are derived from relevant content and configuration hashes. A completed stage is reused when its inputs and implementation version have not changed.

Only transient failures are retried, using capped exponential backoff with jitter. Invalid data, unsupported documents, and schema failures are recorded and routed for correction or review rather than retried blindly.

Batch execution uses bounded download concurrency, process-level parallelism only where parsing benefits, low-concurrency asynchronous LLM calls, centralized database writes, and checkpoints.

## 9. Structured Extraction and Evidence

Regex and LLM extractors return the same `ProjectExtraction` contract. Field groups initially cover:

- Identity.
- Parties.
- Methodology.
- Technical design.
- Carbon accounting.
- Monitoring.
- Project lifecycle.
- Fields required by the legacy 12-dimension framework.

A material extracted value contains both the value and its evidence:

```json
{
  "value": 120000,
  "unit": "tCO2e/year",
  "evidence": {
    "document_sha256": "...",
    "page": 18,
    "quote": "..."
  }
}
```

If a value is absent, the extractor returns `null` with a controlled missing reason. It must not infer unsupported values.

Structured output constrains shape, not truth. Therefore validation occurs in layers:

1. Pydantic structure, types, enums, and ranges.
2. Evidence document, page, and normalized quote containment.
3. Carbon-domain rules.
4. Cross-field consistency.
5. Cross-document and cross-version consistency.
6. Human review for material unresolved cases.

Candidate page selection initially uses deterministic document structure and keyword heuristics. It is not labeled RAG because it does not use embeddings, a retriever, or semantic vector search.

## 10. Canonicalization

Canonicalization preserves rather than erases disagreement. Each canonical field stores:

- Accepted value.
- All candidate observations.
- Evidence used.
- Selection rule and rule version.
- Rejected candidates and reasons.
- Conflict and review status.

Source priority is field-specific, not a single global document ranking. Registry metadata is often authoritative for registry identifiers and current status, while the latest valid official project or monitoring document may be authoritative for other fields. Every priority rule must be explicit and versioned.

## 11. Assessment Architecture

Three assessment paths are retained:

### 11.1 Legacy Keyword Baseline

The old regex and keyword logic is preserved under an explicit name such as `LegacyKeywordBaselineScorer`. Its former `coverage_ratio` is renamed `legacy_keyword_score_ratio`, because it measures keyword points divided by maximum keyword points rather than data completeness.

### 11.2 Evidence-based Deterministic Assessment

Validated facts are mapped to scores through versioned rubrics. Each dimension defines:

- Required facts.
- Evidence requirements.
- Eligibility gates.
- Score levels.
- Missing-data policy.
- Weight.
- Rule identifiers.

The standard scale remains compatible with the legacy 0-3 dimensions, while allowing `ABSTAIN` and `REVIEW_REQUIRED` states.

### 11.3 LLM-assisted Criteria

For genuinely semantic criteria, an LLM may return a constrained intermediate judgment such as `met`, `partially_met`, `weak`, `not_met`, or `unclear`, along with evidence and reasoning. A deterministic rubric maps the validated judgment to points. The LLM does not assign the aggregate score.

A `ScoringRun` records rubric version, canonical-record hash, dimension breakdown, evidence, rules used, explanations, conflicts, total score, normalized score, and scoring coverage.

Data-quality metrics remain separate from project assessment:

- Field completeness.
- Evidence-grounding rate.
- Validation pass rate.
- Conflict count.
- Scoring coverage.
- Project assessment score.

## 12. Evaluation Strategy

Evaluation is layered rather than summarized by one accuracy number.

### 12.1 Deterministic Tests

- Hash stability and deduplication.
- Version association.
- Unit and date normalization.
- Schema rejection behavior.
- Scoring calculations.
- Database constraints.
- Idempotent re-execution.

### 12.2 Pipeline Integration Tests

Local fixtures exercise ingestion through persistence without live registries or online LLM calls. Tests cover stage handoff, checkpoints, failure records, OCR routing, and end-to-end provenance.

### 12.3 Extraction Evaluation

Metrics are selected by field type:

- Exact match for stable identifiers.
- Normalized exact match for dates and units.
- Numeric tolerance for quantities.
- Precision, recall, and F1 for multi-valued fields.
- Rubric evaluation for complex semantic fields.
- Missingness accuracy.

### 12.4 Evidence Evaluation

- Correct document rate.
- Correct page rate.
- Quote-containment rate.
- Field-evidence consistency.
- Unsupported-claim rate.

### 12.5 Scoring Evaluation

Legacy baseline, evidence-based scoring, and human labels are compared per dimension using exact agreement, mean absolute error, weighted Cohen's kappa, ranking correlation, coverage, and false-confidence rate.

### 12.6 Validation Evaluation

Synthetic and curated failures measure error-detection recall and false positives for invalid numbers, dates, methodology identifiers, evidence references, units, registry conflicts, and document versions.

### 12.7 Dataset Discipline

The initial gold set contains 3-5 ACM0002 projects from each of ACR, Gold Standard, and VCS. It deliberately includes clean text, scanned pages, tables, multiple versions, missing fields, conflicting sources, and difficult organization names.

Development and frozen test sets are separate. Test-set inspection followed by prompt tuning is treated as evaluation leakage and requires a new held-out evaluation set.

## 13. LLMOps and Cost Control

Every real model call records:

- Provider and model.
- Prompt version and hash.
- Schema version.
- Input document and selected-pages hashes.
- Input and output tokens.
- Estimated cost.
- Latency.
- Retry count and final status.

Prompt files live under version control rather than being scattered through Python strings.

The cache key includes document, selected pages, prompt, schema, and model identities. Unchanged inputs do not incur repeated calls.

Cost controls include:

- Deterministic page selection before LLM invocation.
- Model routing only after evaluation.
- Per-project call, token, cost, retry, and agent-action budgets.
- Human escalation after bounded failure rather than unlimited loops.

## 14. AI Product Layer and Human Review

The product is designed for carbon-data analysts and reviewers who need to turn heterogeneous registry records and documents into defensible structured assessments.

The review console will support:

- Project and processing-status lists.
- Side-by-side extracted values and source evidence.
- Schema and business-rule errors.
- Cross-document conflicts.
- Accept, correct, reject, and escalate actions.
- Final score explanation and audit history.

Human actions create structured feedback containing the model result, reviewer result, reason, evidence, and model/prompt versions. Feedback becomes evaluation data only after curation; it is not automatically treated as agent memory or a production rule.

Product metrics include:

- Analyst handling time per project.
- Time to a usable assessment.
- Review actions per project.
- Acceptance and correction rates.
- Pipeline success and retry rates.
- Extraction, evidence, and hallucination metrics.
- Cost per document, project, extracted field, and usable assessment.

## 15. Review Agent Boundary

The standard data path remains a workflow. A `Carbon Project Review Agent` may be introduced for exception investigation only after:

- The normal workflow is stable.
- All tools have tested input and output contracts.
- Recurrent exception categories have been measured.
- Fixed rules cannot economically cover them.
- Agent evaluation cases and stopping conditions exist.
- Tool-call and token budgets exist.
- Outputs remain subject to normal validation.

Potential tools include document listing, metadata inspection, parsing, OCR, structured extraction, text search, version comparison, evidence validation, scoring, and human-review escalation.

A genuine agent must maintain state and select actions from observations until it resolves the goal or reaches a stop/escalation condition. A fixed sequence of function calls remains a workflow even if implemented with an agent framework.

Agent evaluation includes task success, valid tool selection, unnecessary calls, grounded resolution, unsafe field changes, escalation calibration, latency, and cost.

## 16. Technology Decisions

The recommended implementation is a Python modular monolith:

- Python 3.12 or later.
- `uv` and `pyproject.toml` for dependency and environment management.
- Pydantic for domain validation and generated JSON Schema.
- SQLite behind SQLAlchemy repositories for the MVP.
- Alembic for database migrations.
- HTTPX for registry and document HTTP operations.
- PyMuPDF for page-level parsing.
- A Tesseract-backed OCR adapter, invoked only after text-quality checks.
- Typer for the initial CLI.
- pytest for unit, integration, and evaluation tests.
- Ruff for formatting and static checks.
- Standard Python logging with structured JSON output.
- A provider-neutral structured-extractor protocol with fake and real adapters.

An orchestration framework, microservices, a distributed queue, and an agent framework are deferred until measured requirements justify them.

## 17. Repository Layout

```text
catchain/
  pyproject.toml
  uv.lock
  README.md
  .env.example
  configs/
    registries/
    prompts/
    scoring/
  schemas/generated/
  src/catchain/
    domain/
    ingestion/
    parsing/
    extraction/baseline/
    extraction/llm/
    validation/
    canonicalization/
    scoring/
    storage/
    evaluation/
    orchestration/
    cli.py
  tests/
    fixtures/
    unit/
    integration/
    evaluation/
  data/
    raw/
    parsed/
    extracted/
    catchain.sqlite
  docs/
    architecture/
    audit/
    decisions/
    learning/
    superpowers/specs/
    superpowers/plans/
```

Large source documents, runtime databases, credentials, and private data are excluded from version control. Small, licensed fixtures may be committed for reproducible tests.

The new project is an independent Git repository at:

```text
/Users/jiangchunlin/Documents/ChatGPT/学习/catchain
```

Legacy repositories remain unchanged and are imported only through explicit, provenance-recorded migration steps.

## 18. MVP Scope and Acceptance Criteria

The MVP operates on a frozen set of 9-15 ACM0002 projects: 3-5 each from ACR, Gold Standard, and VCS.

It includes metadata, local or remote document import, hashes, versions, Raw/Parsed/Extracted layers, parsing, OCR fallback, regex baseline, keyword baseline, Pydantic schemas, evidence validation, SQLite, one real LLM adapter, offline regex-versus-LLM evaluation, the migrated 12-dimension framework, CLI commands, a minimal review console, tests, an initial gold set, and run/cost logging.

The MVP is accepted when the same fixed project can be reprocessed without duplicate artifacts; document versions are identifiable; baseline and LLM outputs share a schema; material fields lead to source evidence; invalid candidates cannot enter canonical data; assessment is reproducible and explainable; outputs can be compared with human labels; a reviewer can accept, correct, or reject a candidate while preserving an audit record; and cost, latency, and failure reasons are observable.

## 19. Implementation Slices

1. Repository foundation, domain models, generated schema, and tests.
2. Raw ingestion, SHA-256, deduplication, versions, and SQLite.
3. Parsed layer, page-quality checks, and OCR fallback.
4. Migration of regex extraction and keyword-scoring baselines.
5. Provider-neutral and real LLM structured extraction.
6. Evidence, domain, conflict validation, and canonicalization.
7. Versioned 12-dimension assessment and human comparison.
8. Review console, feedback capture, and product analytics.
9. Review agent only after its entry criteria are met.

Each slice follows the same teaching loop:

1. Inspect real input.
2. Explain the concept in plain language.
3. Define inputs, outputs, and failure modes.
4. Write focused tests.
5. Implement a small core change.
6. Run it and inspect real output.
7. Compare with the legacy implementation where relevant.
8. Perform error analysis.
9. Write a project-linked learning note.
10. Confirm that the owner can explain why the code exists and what deletion would break.

## 20. Learning Map

- Foundation and ingestion: data pipelines, ETL/ELT, hashing, idempotency, databases, provenance, batch processing, retry, and logging.
- Baseline: regex, heuristics, precision, recall, F1, and error analysis.
- LLM extraction: tokens, tokenizers, Transformer, self-attention, inference, context windows, prompts, system prompts, few-shot examples, structured output, and cost.
- Validation: Pydantic, JSON Schema, hallucination, grounding, evidence, uncertainty, and human review.
- Assessment: classification versus scoring, rubrics, agreement, evaluation leakage, and explainability.
- Product: users, workflows, quality/latency/cost trade-offs, feedback loops, MVP metrics, and experiments.
- Agent: workflow versus agent, tool calling, state, observation/action loops, ReAct, stop conditions, context engineering, escalation, and agent evaluation.
- Optional experiments: chunking, embeddings, cosine similarity, semantic search, retrievers, vector databases, RAG, memory, reflection, planning, MCP, and multi-agent collaboration. These enter the production architecture only if a CATchain requirement justifies them.

## 21. Risks and Mitigations

### Scope expansion

Mitigation: enforce slice acceptance criteria and defer advanced frameworks.

### Poor or unavailable source documents

Mitigation: immutable raw storage, typed failures, OCR fallback, abstention, and review queues.

### LLM hallucination

Mitigation: constrained output, mandatory evidence, quote validation, cross-source checks, canonicalization gates, and unsupported-claim metrics.

### Misleading assessment

Mitigation: separate data quality from project quality, preserve abstention, version rubrics, expose dimension evidence, and compare against human labels.

### Evaluation leakage

Mitigation: separate development and frozen test sets, track dataset versions, and create new holdouts after test-driven tuning.

### Provider lock-in and cost drift

Mitigation: internal protocols, cached runs, versioned metadata, bounded budgets, and provider comparison through the same evaluation set.

### Learning becoming secondary to code production

Mitigation: keep implementation increments small, require learning notes, review real inputs and outputs, and explicitly explain each core component's purpose and failure behavior.

## 22. Decision Record

The following decisions are approved:

- Build a new independent repository rather than modifying the legacy prototype.
- Use a Python modular monolith for the MVP.
- Preserve legacy regex and keyword scoring as baselines.
- Treat the production data path as a workflow.
- Add an exception-focused review agent only when justified by measured cases.
- Use Pydantic models as the schema source of truth.
- Use SQLite behind repository interfaces initially.
- Keep source documents immutable and versioned by content identity.
- Require field-level evidence for material extracted facts.
- Separate extraction, validation, canonicalization, and scoring.
- Separate data quality, assessment score, and scoring coverage.
- Evaluate each layer with task-appropriate metrics.
- Develop through small, testable, tutorial-oriented slices.

## 23. Deferred Decisions

The design intentionally leaves the following choices until the relevant slice provides real evidence:

- The first production LLM provider, selected from available credentials and a common structured-extraction evaluation rather than provider preference.
- The review-console framework, selected after the review workflow and required interactions are validated through the CLI and fixtures.
- The exact wording, weights, and evidence thresholds of all 12 dimensions, finalized only after a dimension-by-dimension audit of the legacy rules.
- Live registry collection schedules, rate limits, and terms-of-use handling, finalized before enabling recurrent external collection.
- Any RAG or agent framework, selected only after entry criteria show a production need.

These are deferred implementation decisions, not permission to change the approved product boundary.

## 24. References

- Carbon Methodology Archive: <https://github.com/Doerp/carbon-methodology-archive>
- Hello-Agents: <https://github.com/datawhalechina/hello-agents>
- uv project documentation: <https://docs.astral.sh/uv/concepts/projects/>
- Pydantic JSON Schema documentation: <https://docs.pydantic.dev/latest/concepts/json_schema/>
- SQLAlchemy ORM documentation: <https://docs.sqlalchemy.org/en/20/orm/>
- PyMuPDF OCR documentation: <https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html>
- pytest documentation: <https://docs.pytest.org/en/stable/>
