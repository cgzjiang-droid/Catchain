import json
from importlib.resources import files
from uuid import UUID, uuid4

from test_review import setup
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain import Registry
from catchain.scoring.readiness import project_readiness
from catchain.storage.review_repository import decide


def test_catalog_preserves_12_dimensions_47_inputs_and_no_confirmed_weights():
    policy = json.loads(
        files("catchain.scoring").joinpath("acm0002-readiness-v1.json").read_bytes()
    )
    assert [d["dimension_id"] for d in policy["dimensions"]] == [f"D{i:02}" for i in range(1, 13)]
    assert len({f for d in policy["dimensions"] for f in d["input_fields"]}) == 47
    assert all(d["weight"] is None for d in policy["dimensions"])


def test_unreviewed_candidates_are_not_scoring_facts(tmp_path):
    engine, request = setup(tmp_path)
    report = project_readiness(engine, registry=Registry.VERRA, project_id="VCS1")
    assert not report["facts"] and report["total_score"] is None
    assert all(d["score"] is None and d["status"] == "missing_inputs" for d in report["dimensions"])
    decide(engine, request)
    report = project_readiness(engine, registry=Registry.VERRA, project_id="VCS1")
    fact = report["facts"]["project_name"]
    assert fact["decision_id"] == str(request.decision_id)
    assert fact["evidence"] == [e.model_dump(mode="json") for e in request.after.evidence]
    assert fact["extraction_run_id"] and fact["sha256"] and fact["extraction_method"]
    other = project_readiness(engine, registry=Registry.VERRA, project_id="another")
    assert other["facts"] == {}


def test_full_input_presence_does_not_imply_quality_score(tmp_path):
    engine, technology = setup(tmp_path, "technology_type", "solar")
    decide(engine, technology)
    engine, resource = setup(tmp_path, "renewable_resource_type", "solar")
    decide(engine, resource)
    engine, capacity = setup(tmp_path, "installed_capacity_mw", 12)
    decide(
        engine,
        capacity.model_copy(update={"after": capacity.after.model_copy(update={"unit": "MW"})}),
    )
    engine, request = setup(tmp_path, "methodology_name", "ACM0002")
    decide(engine, request)
    report = project_readiness(engine, registry=Registry.VERRA, project_id="VCS1")
    assert report["methodology_scope"] == "confirmed_by_reviewed_fact"
    assert report["total_score"] is None and report["accuracy"] is None
    dimension = next(d for d in report["dimensions"] if d["dimension_id"] == "D02")
    assert dimension["missing_fields"] == [] and dimension["status"] == "rubric_pending"
    assert dimension["score"] is None


def test_readiness_cli_reuses_and_tracks_new_current_fact(tmp_path):
    engine, request = setup(tmp_path)
    first = decide(engine, request)
    runner = CliRunner()
    args = [
        "score",
        "readiness",
        "--registry",
        "verra",
        "--project-id",
        "VCS1",
        "--database",
        str(tmp_path / "db.sqlite"),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.exception
    one = json.loads(result.stdout)
    assert json.loads(runner.invoke(app, args).stdout)["status"] == "reused"
    decide(
        engine,
        request.model_copy(
            update={
                "decision_id": uuid4(),
                "expected_current_fact_id": UUID(first["fact_id"]),
                "reason": "New review",
            }
        ),
    )
    two = json.loads(runner.invoke(app, args).stdout)
    assert two["artifact_path"] != one["artifact_path"]
