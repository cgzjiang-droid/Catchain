from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_validation import fixture

from catchain.domain.consistency import ValidationInput
from catchain.domain.documents import DocumentType
from catchain.validation.consistency import validate_project
from catchain.validation.extraction import validate_extraction


def input_for(field, value, *, source=None, unit=None):
    parsed, extraction = fixture(field, value, unit=unit)
    return ValidationInput(
        report=validate_extraction(parsed, extraction, pipeline_run_id=uuid4()),
        source_document_id=source or uuid4(),
        document_type=DocumentType.MONITORING_REPORT,
        sha256="a" * 64,
        declared_version=None,
        retrieved_at=datetime.now(UTC),
    )


def codes(report):
    return {issue.code for issue in report.issues}


def test_version_difference_preserves_both_candidates_and_never_promotes():
    source = uuid4()
    first = input_for("installed_capacity_mw", 12, source=source, unit="MW")
    second = input_for("installed_capacity_mw", 14, source=source, unit="MW")
    report = validate_project((second, first), pipeline_run_id=uuid4())
    assert "cross_version_difference" in codes(report)
    issue = next(i for i in report.issues if i.code == "cross_version_difference")
    assert len(issue.candidates) == 2 and issue.status == "unresolved"
    assert {i.report.checks[0].observation.normalized_value for i in report.inputs} == {12, 14}
    assert report.canonical_writes == 0


def test_document_difference_and_period_specific_dates():
    first = input_for("country", "Brazil")
    second = input_for("country", "India")
    assert "cross_document_difference" in codes(
        validate_project((first, second), pipeline_run_id=uuid4())
    )
    first = input_for("verification_period_start", "2020-01-01")
    second = input_for("verification_period_start", "2021-01-01")
    report = validate_project((first, second), pipeline_run_id=uuid4())
    assert "cross_document_difference" not in codes(report)
    assert "date_pair_incomplete_or_conflicting" in codes(report)


def test_rejected_candidate_is_not_used_in_comparison():
    first = input_for("installed_capacity_mw", -12, unit="MW")
    second = input_for("installed_capacity_mw", 14, unit="MW")
    report = validate_project((first, second), pipeline_run_id=uuid4())
    assert "cross_document_difference" not in codes(report)
    assert first.report.checks[0].status == "rejected"


def test_scope_and_duplicate_inputs_are_rejected():
    first = input_for("country", "Brazil")
    with pytest.raises(ValueError, match="duplicate"):
        validate_project((first, first), pipeline_run_id=uuid4())
    other = first.model_copy(
        update={
            "report": first.report.model_copy(
                update={"project_id": "another", "pipeline_run_id": uuid4()}
            )
        }
    )
    with pytest.raises(ValueError, match="mix"):
        validate_project((first, other), pipeline_run_id=uuid4())


def test_missing_methodology_blocks_business_scope():
    report = validate_project((input_for("country", "Brazil"),), pipeline_run_id=uuid4())
    assert "methodology_scope_unconfirmed" in codes(report)
    assert report.cross_document_comparison == "not_possible"
    confirmed = validate_project(
        (input_for("methodology_name", "ACM0002"),), pipeline_run_id=uuid4()
    )
    assert "methodology_scope_unconfirmed" not in codes(confirmed)
    assert confirmed.canonical_writes == 0


@pytest.mark.parametrize(
    "start,code",
    [
        ("2022-01-01", "date_order_reversed"),
        ("2020", "date_pair_not_evaluable"),
    ],
)
def test_dates_are_compared_without_guessing(start, code):
    parsed, extraction = fixture("crediting_period_start", start)
    first = extraction.observations[0]
    end = first.model_copy(
        update={"field_name": "crediting_period_end", "normalized_value": "2021-01-01"}
    )
    extraction = extraction.model_copy(update={"observations": (first, end)})
    base = input_for("country", "Brazil")
    item = base.model_copy(
        update={"report": validate_extraction(parsed, extraction, pipeline_run_id=uuid4())}
    )
    report = validate_project((item,), pipeline_run_id=uuid4())
    assert code in codes(report)
    issue = next(i for i in report.issues if i.code == code)
    assert len(issue.candidates) == 2 and report.canonical_writes == 0
