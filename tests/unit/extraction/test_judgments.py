import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_review import setup
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain.judgment import CriterionJudgment, JudgmentRequest
from catchain.storage.database import evaluation_results
from catchain.storage.review_repository import decide


def test_decisive_judgment_requires_basis_but_insufficient_can_abstain():
    for outcome in ("supported", "not_supported", "not_applicable"):
        with pytest.raises(ValidationError):
            CriterionJudgment(criterion_id="D01.C1", outcome=outcome, reason="No proof")
    item = CriterionJudgment(
        criterion_id="D01.C1", outcome="insufficient", reason="No project boundary proof"
    )
    with pytest.raises(ValidationError):
        JudgmentRequest(reviewer="reviewer", judgments=(item, item))
    with pytest.raises(ValidationError):
        CriterionJudgment(criterion_id="D01.C9", outcome="insufficient", reason="No proof")


def test_save_judgments_reuse_evidence_and_stale_snapshot(tmp_path):
    engine, request = setup(tmp_path)
    decide(engine, request)
    runner = CliRunner()
    ready = runner.invoke(
        app,
        [
            "score",
            "readiness",
            "--registry",
            "verra",
            "--project-id",
            "VCS1",
            "--database",
            str(tmp_path / "db.sqlite"),
            "--output-dir",
            str(tmp_path / "ready"),
        ],
    )
    assert ready.exit_code == 0, ready.exception
    path = tmp_path / "judgment.json"
    item = CriterionJudgment(
        criterion_id="D01.C1", outcome="insufficient", reason="Name alone is not boundary proof"
    )
    judgment = JudgmentRequest(reviewer="fixture reviewer", judgments=(item,))
    path.write_text(judgment.model_dump_json())
    args = [
        "score",
        "judgments",
        json.loads(ready.stdout)["artifact_path"],
        "--request-file",
        str(path),
        "--database",
        str(tmp_path / "db.sqlite"),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.exception
    info = json.loads(first.stdout)
    assert info["unreviewed_count"] == 35 and info["total_score"] is None
    stored = json.loads(Path(info["artifact_path"]).read_text())
    assert stored["result"]["score_status"] == "pending_policy"
    assert stored["result"]["dimensions"][0]["status"] == "partially_reviewed"
    assert stored["result"]["dimensions"][0]["score"] is None
    assert stored["result"]["dimensions"][0]["unreviewed_criterion_ids"] == [
        "D01.C2",
        "D01.C3",
    ]
    with engine.connect() as connection:
        count = connection.execute(
            select(func.count()).select_from(evaluation_results)
        ).scalar_one()
        assert count == 1
    assert json.loads(runner.invoke(app, args).stdout)["status"] == "reused"
    with engine.connect() as connection:
        count = connection.execute(
            select(func.count()).select_from(evaluation_results)
        ).scalar_one()
        assert count == 1
    from catchain.domain import EvidenceRef

    snapshot = json.loads(Path(json.loads(ready.stdout)["artifact_path"]).read_text())["result"]
    fact = snapshot["facts"]["project_name"]
    quoted = CriterionJudgment(
        criterion_id="D01.C1",
        outcome="insufficient",
        reason="Quoted name is not boundary proof",
        fact_ids=(fact["fact_id"],),
        evidence=tuple(EvidenceRef.model_validate(e) for e in fact["evidence"]),
    )
    path.write_text(JudgmentRequest(reviewer="fixture", judgments=(quoted,)).model_dump_json())
    assert runner.invoke(app, args).exit_code == 0
    wrong = quoted.model_copy(
        update={"evidence": (quoted.evidence[0].model_copy(update={"quote": "invented"}),)}
    )
    path.write_text(JudgmentRequest(reviewer="fixture", judgments=(wrong,)).model_dump_json())
    assert runner.invoke(app, args).exit_code == 1
    from uuid import UUID, uuid4

    unrelated = quoted.model_copy(update={"criterion_id": "D05.C1"})
    path.write_text(JudgmentRequest(reviewer="fixture", judgments=(unrelated,)).model_dump_json())
    assert runner.invoke(app, args).exit_code == 1

    path.write_text(judgment.model_dump_json())
    decide(
        engine,
        request.model_copy(
            update={"decision_id": uuid4(), "expected_current_fact_id": UUID(fact["fact_id"])}
        ),
    )
    assert runner.invoke(app, args).exit_code == 1
