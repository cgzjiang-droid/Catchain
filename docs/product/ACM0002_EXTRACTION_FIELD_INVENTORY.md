# ACM0002 Extraction Field Inventory

Status: shared candidate contract implemented; schema 1.1.0, Slice 4 in progress.

## Sources reviewed

The inventory was reconstructed from the locally available teacher-final package:

- `老师提交_最终_ACM0002_我们Table标准/field_mapping_acm0002_master.json`
- `老师提交_最终_ACM0002_我们Table标准/method_table_acm0002_independent.json`
- `david_template_acm0002/extraction_schema_acm0002.json`
- legacy JSON/CSV extraction outputs and `reef_assessment.json` examples

The teacher-final field mapping contains 12 dimensions and 47 unique canonical
assessment-input fields. Registry and country are also required project identity
fields in the legacy extraction schema.

## Project identity and source context

- `registry`
- `country`
- `project_id`
- `project_name`
- methodology scope: ACM0002
- source document and immutable document-version identity

## D01 — Grid-connected applicability

- `project_id`
- `project_name`
- `grid_connection_status`
- `project_boundary_text`

## D02 — Technology eligibility under ACM0002

- `technology_type`
- `installed_capacity_mw`
- `renewable_resource_type`

## D03 — Baseline construction integrity

- `baseline_scenario_text`
- `baseline_formula_present`
- `baseline_assumptions_table`

## D04 — Grid emission factor chain

- `ef_value`
- `ef_unit`
- `ef_source_reference`
- `ef_vintage_year`

## D05 — Generation/export metering quality

- `electricity_generated_mwh`
- `electricity_exported_mwh`
- `meter_calibration_status`
- `data_frequency`

## D06 — Project emissions treatment

- `pe_applicable_flag`
- `pe_value_tco2e`
- `pe_method_text`

## D07 — Leakage treatment

- `le_applicable_flag`
- `le_value_tco2e`
- `le_justification_text`

## D08 — Emission-reduction formula reproducibility

- `be_value_tco2e`
- `er_reported_tco2e`
- `er_recalculated_tco2e`
- `er_recalc_error_pct`

## D09 — Additionality robustness

- `additionality_tool_used`
- `investment_analysis_result`
- `barrier_analysis_result`
- `common_practice_result`

## D10 — Monitoring architecture completeness

- `monitoring_parameters_listed`
- `qa_qc_procedure_text`
- `data_gap_procedure_text`
- `archiving_period_years`

## D11 — Verification reproducibility and cycle consistency

- `validator_name`
- `verifier_name`
- `verification_period_start`
- `verification_period_end`
- `verification_cycle_count`

## D12 — Registry and version transition readiness

- `methodology_name`
- `methodology_version`
- `registered_date`
- `listed_date`
- `issuance_cycle_count`
- `version_change_note`

## Required envelope for each extracted observation

The new system must not store only the final scalar value. Each candidate observation
needs enough information for validation and human review:

- raw extracted value and normalized value;
- unit where applicable;
- extractor type and extractor/schema version;
- confidence or abstention where meaningful;
- controlled missing reason when no supported value is found;
- evidence containing document-version identity, page, quote, and character offsets;
- validation status and issues;
- review and conflict status;
- original and corrected values plus reviewer identity when humans edit a value.

## Relationship to implementation plan

Slice 3 continues to produce reliable page text. Slice 4 will audit legacy regex and
keyword behavior, define the typed `ProjectExtraction` and `FieldObservation` models
from this inventory, generate their JSON Schemas, and make the regex baseline emit
that contract. Slice 5 will require the LLM extractor to emit the same contract.

The exact 12-dimension scoring rules and weights remain versioned separately from
extraction so that a rubric change does not require re-parsing or re-extracting PDFs.

## Final-delivery business extension (2026-09-17)

47 assessment-input fields plus country and seven new names make 55 observation fields.
Project title reuses project_name; company roles are strings with repeated observations.

| Field | Type | Meaning |
| --- | --- | --- |
| project_participant | string | Explicit participant/proponent label |
| project_owner | string | Explicit owner role |
| project_developer | string | Explicit developer role |
| project_operator | string | Explicit operator role |
| crediting_period_years | integer | Stated duration in years |
| crediting_period_start | string | Raw date, including ambiguous and year-only values |
| crediting_period_end | string | Raw date; no invented month/day |

A raw company label may contain multiple entities; legal-entity splitting, generic
company detection, contact extraction and full location fields remain unmigrated assets.
New schema 1.1.0 requires caller-supplied pipeline_run_id. Old 1.0.0 can be read
without inventing a run ID. validation_status remains unvalidated; Slice 6 supplies
business and evidence checks. Persistent run existence is not yet enforced.
