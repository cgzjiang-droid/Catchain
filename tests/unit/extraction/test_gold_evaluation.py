import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain import (
    EvidenceRef,
    GoldDataset,
    GoldFieldLabel,
    GoldSample,
    PipelineRun,
    PipelineStage,
    ProjectExtraction,
    Registry,
    RunStatus,
)
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


def test_cli_evaluate_gold_stores_and_reuses_result(tmp_path: Path):
    gold, extraction = _fixture()
    run_id = uuid4()
    extraction = extraction.model_copy(update={"pipeline_run_id": run_id})
    run = PipelineRun(
        pipeline_run_id=run_id,
        stage=PipelineStage.BASELINE_EXTRACTED,
        status=RunStatus.SUCCEEDED,
        input_hash=hashlib.sha256(extraction.model_dump_json().encode()).hexdigest(),
        config_hash="a" * 64,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    gold_path = tmp_path / "gold.json"
    artifact_path = tmp_path / "extraction.json"
    gold_path.write_text(gold.model_dump_json())
    artifact_path.write_text(
        json.dumps(
            {"result": extraction.model_dump(mode="json"), "run": run.model_dump(mode="json")}
        )
    )
    args = [
        "evaluate",
        "gold",
        str(gold_path),
        str(artifact_path),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    runner = CliRunner()
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.exception
    info = json.loads(first.stdout)
    assert info["metrics"]["accuracy"] == 1
    assert json.loads(runner.invoke(app, args).stdout)["status"] == "reused"


def test_cli_evaluate_dataset_requires_complete_frozen_split(tmp_path: Path):
    gold, extraction = _fixture()
    dataset = GoldDataset(
        dataset_version=gold.dataset_version,
        samples=(gold,),
        status="frozen",
        frozen_at=datetime.now(UTC),
    )
    report = evaluate_against_gold(gold, extraction)
    dataset_path = tmp_path / "dataset.json"
    reports = tmp_path / "reports"
    reports.mkdir()
    dataset_path.write_text(dataset.model_dump_json())
    (reports / "one.json").write_text(json.dumps({"result": report}))
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "evaluate",
            "dataset",
            str(dataset_path),
            str(reports),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.exception
    assert json.loads(result.stdout)["metrics"]["samples_evaluated"] == 1
