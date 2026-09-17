from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from catchain.domain import EvidenceRef, FieldObservation, ProjectExtraction, Registry


def test_candidate_contract_preserves_evidence_and_rejects_unsupported_values():
    version = uuid4()
    evidence = EvidenceRef(
        document_version_id=version,
        page_number=1,
        quote="12.5 MW",
        char_start=0,
        char_end=7,
    )
    candidate = FieldObservation(
        field_name="installed_capacity_mw",
        raw_value="12.5",
        normalized_value=12.5,
        unit="MW",
        evidence=(evidence,),
    )
    extraction = ProjectExtraction(
        project_id="VCS7",
        registry=Registry.VERRA,
        document_version_id=version,
        parsed_document_id=uuid4(),
        extractor_name="regex",
        extractor_version="1",
        schema_version="1.0.0",
        created_at=datetime.now(UTC),
        observations=(candidate,),
    )
    assert ProjectExtraction.model_validate_json(extraction.model_dump_json()) == extraction
    assert candidate.confidence is None
    false_candidate = FieldObservation(
        field_name="pe_applicable_flag",
        raw_value="false",
        normalized_value=False,
        evidence=(evidence,),
    )
    assert false_candidate.normalized_value is False
    assert (
        FieldObservation(
            field_name="pe_value_tco2e",
            raw_value="0",
            normalized_value=0,
            evidence=(evidence,),
        ).normalized_value
        == 0
    )
    assert (
        FieldObservation(
            field_name="registered_date",
            missing_reason="unsupported_by_baseline",
        ).normalized_value
        is None
    )
    for changes in (
        {"evidence": ()},
        {"raw_value": None},
        {"normalized_value": None},
        {"missing_reason": "not_found"},
        {"confidence": 1.1},
        {"field_name": "invented_field"},
    ):
        with pytest.raises(ValidationError):
            FieldObservation.model_validate(candidate.model_dump() | changes)
    with pytest.raises(ValidationError):
        ProjectExtraction.model_validate(extraction.model_dump() | {"document_version_id": uuid4()})
    with pytest.raises(ValidationError):
        ProjectExtraction.model_validate(extraction.model_dump() | {"schema_version": "1.1.0"})
    new = ProjectExtraction.model_validate(
        extraction.model_dump() | {"schema_version": "1.1.0", "pipeline_run_id": uuid4()}
    )
    assert new.pipeline_run_id is not None
