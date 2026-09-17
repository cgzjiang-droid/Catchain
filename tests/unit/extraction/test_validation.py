from datetime import UTC, datetime
from uuid import uuid4

import pytest

from catchain.domain import (
    EvidenceRef,
    FieldObservation,
    ParsedDocument,
    ParsedPage,
    ProjectExtraction,
    Registry,
)
from catchain.parsing.quality import measure_text_quality
from catchain.validation.extraction import validate_extraction


def fixture(field, value, *, confidence=None, unit=None):
    text = f"Recorded value: {value}"
    parsed = ParsedDocument(
        document_version_id=uuid4(),
        parser_name="fixture",
        parser_version="1",
        created_at=datetime.now(UTC),
        pages=(
            ParsedPage(
                page_number=1,
                text=text,
                char_start=0,
                char_end=len(text),
                quality=measure_text_quality(text),
            ),
        ),
    )
    observation = FieldObservation(
        field_name=field,
        raw_value=str(value),
        normalized_value=value,
        confidence=confidence,
        unit=unit,
        evidence=(
            EvidenceRef(
                document_version_id=parsed.document_version_id,
                page_number=1,
                quote=text,
                char_start=0,
                char_end=len(text),
            ),
        ),
    )
    extraction = ProjectExtraction(
        project_id="VCS1",
        registry=Registry.VERRA,
        document_version_id=parsed.document_version_id,
        parsed_document_id=parsed.parsed_document_id,
        extractor_name="fixture",
        extractor_version="1",
        pipeline_run_id=uuid4(),
        created_at=datetime.now(UTC),
        observations=(observation,),
    )
    return parsed, extraction


@pytest.mark.parametrize(
    "field,value,code,status",
    [
        ("installed_capacity_mw", True, "field_type_invalid", "rejected"),
        ("installed_capacity_mw", "12", "field_type_invalid", "rejected"),
        ("installed_capacity_mw", -12, "numeric_range_invalid", "rejected"),
        ("registered_date", "2023-02-29", "date_calendar_invalid", "rejected"),
        ("registered_date", "03/04/2020", "date_format_unresolved", "needs_review"),
        ("registered_date", "2020", "date_format_unresolved", "needs_review"),
    ],
)
def test_field_types_ranges_and_dates_preserve_bad_candidate(field, value, code, status):
    parsed, extraction = fixture(field, value)
    before = extraction.model_dump_json()
    report = validate_extraction(parsed, extraction, pipeline_run_id=uuid4())
    check = report.checks[0]
    assert check.status == status and code in {issue.code for issue in check.issues}
    assert check.observation.normalized_value == value
    assert extraction.model_dump_json() == before and report.canonical_writes == 0


def test_high_confidence_and_exact_evidence_do_not_approve_semantics():
    parsed, extraction = fixture("registered_date", "2024-02-29", confidence=0.99)
    report = validate_extraction(parsed, extraction, pipeline_run_id=uuid4())
    assert report.checks[0].status == "needs_review"
    assert {issue.code for issue in report.checks[0].issues} == {"semantic_support_pending"}


def test_low_confidence_units_conflicts_and_abstentions_remain_separate():
    parsed, extraction = fixture("installed_capacity_mw", 12, confidence=0.79)
    first = extraction.observations[0]
    second = first.model_copy(update={"normalized_value": 14})
    missing = FieldObservation(field_name="country", missing_reason="not_found")
    extraction = extraction.model_copy(update={"observations": (first, second, missing)})
    report = validate_extraction(parsed, extraction, pipeline_run_id=uuid4())
    assert [check.status for check in report.checks] == ["needs_review", "needs_review", "missing"]
    assert {"candidate_conflict", "unit_unverified", "confidence_below_threshold"} <= {
        issue.code for issue in report.checks[0].issues
    }


def test_bad_evidence_and_wrong_artifact_identity_are_blocked():
    parsed, extraction = fixture("project_name", "Example Project")
    original = extraction.observations[0]
    bad_ref = original.evidence[0].model_copy(update={"quote": "invented quote"})
    bad = extraction.model_copy(
        update={"observations": (original.model_copy(update={"evidence": (bad_ref,)}),)}
    )
    report = validate_extraction(parsed, bad, pipeline_run_id=uuid4())
    assert report.checks[0].status == "rejected"
    assert "evidence_quote_missing" in {issue.code for issue in report.checks[0].issues}
    with pytest.raises(ValueError):
        validate_extraction(
            parsed,
            extraction.model_copy(update={"parsed_document_id": uuid4()}),
            pipeline_run_id=uuid4(),
        )


def test_unsettled_business_contract_is_reviewed_instead_of_inventing_a_type():
    parsed, extraction = fixture("baseline_assumptions_table", True)
    report = validate_extraction(parsed, extraction, pipeline_run_id=uuid4())
    assert report.checks[0].status == "needs_review"
    assert "field_contract_pending" in {issue.code for issue in report.checks[0].issues}
