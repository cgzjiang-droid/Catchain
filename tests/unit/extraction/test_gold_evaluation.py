from datetime import UTC, datetime
from uuid import uuid4

import pytest

from catchain.domain import EvidenceRef, GoldFieldLabel, GoldSample, ProjectExtraction, Registry
from catchain.extraction.gold_evaluation import evaluate_against_gold


def _fixture(status="frozen"):
    document_version_id = uuid4()
    parsed_document_id = uuid4()
    evidence = EvidenceRef(
        document_version_id=document_version_id,
        page_number=1,
        quote="Solar project",
        char_start=0,
        char_end=13,
    )
    label = GoldFieldLabel(
        field_name="project_name",
        status="confirmed",
        value="Solar project",
        evidence=(evidence,),
        reason="Reviewed source",
    )
    gold = GoldSample(
        dataset_version="gold-v1",
        sample_id="sample-1",
        split="validation",
        registry=Registry.ACR,
        project_id="VCS1",
        document_version_id=document_version_id,
        parsed_document_id=parsed_document_id,
        labels=(label,),
        reviewers=("a", "b"),
        status=status,
        adjudicator="lead" if status == "frozen" else None,
        frozen_at=datetime.now(UTC) if status == "frozen" else None,
    )
    extraction = ProjectExtraction(
        project_id="VCS1",
        registry=Registry.ACR,
        document_version_id=document_version_id,
        parsed_document_id=parsed_document_id,
        extractor_name="regex",
        extractor_version="test",
        pipeline_run_id=uuid4(),
        created_at=datetime.now(UTC),
        observations=(
            {
                "field_name": "project_name",
                "raw_value": "Solar project",
                "normalized_value": "Solar project",
                "evidence": [evidence.model_dump(mode="json")],
            },
        ),
    )
    return gold, extraction


def test_evaluate_frozen_gold_reports_exact_agreement():
    gold, extraction = _fixture()
    result = evaluate_against_gold(gold, extraction)
    assert result["gold_status"] == "frozen"
    assert result["metrics"]["accuracy"] == 1
    assert result["rows"][0]["outcome"] == "exact_match"


def test_non_frozen_gold_cannot_produce_accuracy():
    gold, extraction = _fixture(status="draft")
    with pytest.raises(ValueError, match="only frozen"):
        evaluate_against_gold(gold, extraction)
