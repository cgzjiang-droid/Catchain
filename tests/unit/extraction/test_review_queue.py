import json

from test_review import setup
from typer.testing import CliRunner

from catchain.cli import app
from catchain.review_queue import build_review_metrics, build_review_queue
from catchain.storage.review_repository import decide


def test_queue_prioritizes_issues_and_preserves_evidence(tmp_path):
    engine, request = setup(tmp_path)

    snapshot = build_review_queue(engine)

    assert len(snapshot.items) == 1
    item = snapshot.items[0]
    assert item.candidate_id == request.candidate_id
    assert item.review_state == "pending"
    assert item.priority == "normal"
    assert "semantic_support_pending" in item.issue_codes
    assert item.evidence_count == 1
    assert item.evidence[0].quote == "Recorded value: Example"
    assert item.current_fact_id is None


def test_approved_candidate_leaves_action_queue_and_metrics_are_explicit(tmp_path):
    engine, request = setup(tmp_path)
    decide(engine, request)

    assert build_review_queue(engine).items == ()
    metrics = build_review_metrics(engine)
    assert metrics.total_candidates == 1
    assert metrics.reviewed_candidates == 1
    assert metrics.pending_candidates == 0
    assert metrics.decisions_by_status == {"approved": 1}
    assert metrics.approval_rate == 1
    assert metrics.unresolved_rate == 0
    assert metrics.evidence_coverage == 1
    assert metrics.field_coverage == 1
    assert metrics.average_review_latency_seconds is not None
    assert metrics.accuracy_eligible is False
    assert metrics.total_score_eligible is False


def test_review_cli_writes_content_addressed_queue_and_metrics(tmp_path):
    engine, _request = setup(tmp_path)
    database = tmp_path / "db.sqlite"
    runner = CliRunner()

    queue_args = [
        "review",
        "queue",
        "--database",
        str(database),
        "--output-dir",
        str(tmp_path / "queue"),
    ]
    first = runner.invoke(app, queue_args)
    second = runner.invoke(app, queue_args)
    assert first.exit_code == 0, first.exception
    assert second.exit_code == 0, second.exception
    assert json.loads(first.stdout)["status"] == "stored"
    assert json.loads(second.stdout)["status"] == "reused"

    metrics = runner.invoke(
        app,
        [
            "review",
            "metrics",
            "--database",
            str(database),
            "--output-dir",
            str(tmp_path / "metrics"),
        ],
    )
    assert metrics.exit_code == 0, metrics.exception
    result = json.loads(metrics.stdout)
    assert result["total_candidates"] == 1
    assert result["accuracy_eligible"] is False

