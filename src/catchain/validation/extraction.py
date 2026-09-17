"""Mechanical validation: exact evidence and domain shape, not semantic approval."""

import json
import math
import re
from datetime import date
from typing import get_args
from uuid import UUID

from catchain.domain import ParsedDocument, ProjectExtraction
from catchain.domain.extraction import FieldName
from catchain.domain.validation import (
    CandidateValidation,
    ExtractionValidationReport,
    ValidationIssue,
)

DATE_FIELDS = {
    field for field in get_args(FieldName) if field.endswith("_start") or field.endswith("_end")
}
DATE_FIELDS |= {"registered_date", "listed_date"}
INTEGER_FIELDS = {
    "ef_vintage_year",
    "archiving_period_years",
    "verification_cycle_count",
    "issuance_cycle_count",
    "crediting_period_years",
}
BOOLEAN_FIELDS = {
    "baseline_formula_present",
    "pe_applicable_flag",
    "le_applicable_flag",
}
NUMBER_FIELDS = {
    "installed_capacity_mw",
    "ef_value",
    "electricity_generated_mwh",
    "electricity_exported_mwh",
    "pe_value_tco2e",
    "le_value_tco2e",
    "be_value_tco2e",
    "er_reported_tco2e",
    "er_recalculated_tco2e",
    "er_recalc_error_pct",
}
EXPECTED_UNITS = {
    "installed_capacity_mw": "MW",
    "electricity_generated_mwh": "MWh",
    "electricity_exported_mwh": "MWh",
    "pe_value_tco2e": "tCO2e",
    "le_value_tco2e": "tCO2e",
    "be_value_tco2e": "tCO2e",
    "er_reported_tco2e": "tCO2e",
    "er_recalculated_tco2e": "tCO2e",
}
TEXT_FIELDS = {
    "project_id",
    "project_name",
    "country",
    "grid_connection_status",
    "technology_type",
    "renewable_resource_type",
    "ef_unit",
    "ef_source_reference",
    "data_frequency",
    "validator_name",
    "verifier_name",
    "methodology_name",
    "methodology_version",
    "version_change_note",
    "project_participant",
    "project_owner",
    "project_developer",
    "project_operator",
}


def validate_extraction(
    parsed: ParsedDocument,
    extraction: ProjectExtraction,
    *,
    pipeline_run_id: UUID,
    confidence_threshold: float = 0.8,
) -> ExtractionValidationReport:
    if not math.isfinite(confidence_threshold) or not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence threshold must be finite and between zero and one")
    if (
        extraction.parsed_document_id != parsed.parsed_document_id
        or extraction.document_version_id != parsed.document_version_id
        or extraction.pipeline_run_id is None
    ):
        raise ValueError("extraction has no matching Parsed/run identity")
    candidates = {}
    for observation in extraction.observations:
        if observation.missing_reason is None:
            candidates.setdefault(observation.field_name, set()).add(
                json.dumps([observation.normalized_value, observation.unit], sort_keys=True)
            )
    checks = []
    for index, observation in enumerate(extraction.observations):
        issues = []

        def add(code, severity, message, items=issues):
            items.append(ValidationIssue(code=code, severity=severity, message=message))

        field, value = observation.field_name, observation.normalized_value
        for evidence in observation.evidence:
            if evidence.document_version_id != parsed.document_version_id:
                add(
                    "evidence_version_invalid",
                    "error",
                    "Evidence belongs to another document version.",
                )
                continue
            if not 1 <= evidence.page_number <= len(parsed.pages):
                add("evidence_page_invalid", "error", "Evidence page is outside source PDF.")
                continue
            text = parsed.pages[evidence.page_number - 1].text
            if not evidence.quote.strip() or evidence.quote not in text:
                add("evidence_quote_missing", "error", "Quote is absent from the stated page.")
            elif evidence.char_start is None or evidence.char_end is None:
                add("evidence_offsets_missing", "review", "Quote needs exact character positions.")
            elif (
                evidence.char_end > len(text)
                or text[evidence.char_start : evidence.char_end] != evidence.quote
            ):
                add("evidence_offsets_invalid", "error", "Character positions do not match quote.")
        if observation.missing_reason is not None:
            if observation.missing_reason == "ambiguous":
                add("ambiguous_abstention", "review", "Extractor could not resolve this field.")
        else:
            is_text = field in DATE_FIELDS | TEXT_FIELDS or field.endswith("_text")
            valid_type = (
                type(value) is bool
                if field in BOOLEAN_FIELDS
                else type(value) is int
                if field in INTEGER_FIELDS
                else type(value) in (int, float)
                if field in NUMBER_FIELDS
                else type(value) is str and bool(value.strip())
                if is_text
                else True
            )
            if field not in INTEGER_FIELDS | NUMBER_FIELDS | BOOLEAN_FIELDS and not is_text:
                add(
                    "field_contract_pending",
                    "review",
                    "Business field type still requires definition.",
                )
            if not valid_type:
                add("field_type_invalid", "error", "Value type does not match field contract.")
            elif field in INTEGER_FIELDS | NUMBER_FIELDS:
                if (field in INTEGER_FIELDS and value < 0) or (
                    field == "installed_capacity_mw" and value <= 0
                ):
                    add("numeric_range_invalid", "error", "Value is outside supported field range.")
                elif value < 0:
                    add(
                        "negative_value_requires_domain_rule",
                        "review",
                        "Confirm signed-value meaning against the field-specific business rule.",
                    )
            elif field in DATE_FIELDS:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    add(
                        "date_format_unresolved",
                        "review",
                        "Require complete YYYY-MM-DD; do not guess.",
                    )
                else:
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        add("date_calendar_invalid", "error", "Date does not exist in calendar.")
            if field in EXPECTED_UNITS and observation.unit != EXPECTED_UNITS[field]:
                add(
                    "unit_unverified",
                    "review",
                    "Unit requires confirmation; no automatic conversion.",
                )
            if observation.confidence is None:
                add("confidence_unknown", "review", "No calibrated confidence is available.")
            elif observation.confidence < confidence_threshold:
                add(
                    "confidence_below_threshold",
                    "review",
                    "Confidence is below configured review threshold.",
                )
            if len(candidates[field]) > 1:
                add("candidate_conflict", "review", "Different candidates remain for this field.")
            add(
                "semantic_support_pending",
                "review",
                "Quote existence does not establish semantic support.",
            )
        status = (
            "rejected"
            if any(issue.severity == "error" for issue in issues)
            else "needs_review"
            if issues
            else "missing"
        )
        checks.append(
            CandidateValidation(
                observation_index=index,
                observation=observation,
                status=status,
                issues=tuple(issues),
            )
        )
    return ExtractionValidationReport(
        pipeline_run_id=pipeline_run_id,
        extraction_run_id=extraction.pipeline_run_id,
        parsed_document_id=parsed.parsed_document_id,
        document_version_id=parsed.document_version_id,
        project_id=extraction.project_id,
        registry=extraction.registry,
        checks=tuple(checks),
    )
