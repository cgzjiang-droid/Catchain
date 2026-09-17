import json
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_review import setup
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain import EvidenceRef, Registry
from catchain.domain.assessment import AssessmentContext
from catchain.scoring.business_checks import ER_FIELDS, check_business_inputs
from catchain.scoring.readiness import project_readiness
from catchain.storage.document_repository import SqlAlchemyDocumentRepository
from catchain.storage.review_repository import decide


def fixture_context(tmp_path, reported=85):
    for field, value in [
        ("methodology_name", "ACM0002"),
        ("methodology_version", "fixture-v1"),
        ("verification_period_start", "2020-01-01"),
        ("verification_period_end", "2020-12-31"),
        ("be_value_tco2e", 100),
        ("pe_value_tco2e", 10),
        ("le_value_tco2e", 5),
        ("er_reported_tco2e", reported),
    ]:
        engine, request = setup(tmp_path, field, value)
        if field in ER_FIELDS:
            request = request.model_copy(
                update={"after": request.after.model_copy(update={"unit": "tCO2e"})}
            )
        decide(engine, request)
    readiness = project_readiness(engine, registry=Registry.VERRA, project_id="VCS1")
    facts = readiness["facts"]
    context = AssessmentContext(
        reviewer="fixture reviewer",
        reason="Synthetic same-period arithmetic test",
        authority_confirmed=True,
        methodology_fact_id=facts["methodology_name"]["fact_id"],
        methodology_version_fact_id=facts["methodology_version"]["fact_id"],
        period_start="2020-01-01",
        period_end="2020-12-31",
        period_fact_ids={f: facts[f]["fact_id"] for f in ER_FIELDS},
        evidence=tuple(
            EvidenceRef.model_validate(e)
            for f in ("verification_period_start", "verification_period_end")
            for e in facts[f]["evidence"]
        ),
    )
    return readiness, context, SqlAlchemyDocumentRepository(engine)


def test_scoped_arithmetic_is_diagnostic_not_score(tmp_path):
    readiness, context, documents = fixture_context(tmp_path, reported=90)
    result = check_business_inputs(readiness, context=context, documents=documents)
    assert not result["gates"]
    assert result["er_diagnostic"]["recalculated"] == "85"
    assert result["er_diagnostic"]["reported_minus_recalculated"] == "5"
    assert result["total_score"] is None and all(d["score"] is None for d in result["dimensions"])


def test_missing_context_and_old_fact_ids_block_recalculation(tmp_path):
    readiness, context, documents = fixture_context(tmp_path)
    assert (
        check_business_inputs(readiness, context=None, documents=documents)["er_diagnostic"][
            "status"
        ]
        == "blocked"
    )
    changed = context.model_copy(
        update={"period_fact_ids": {**context.period_fact_ids, "pe_value_tco2e": uuid4()}}
    )
    result = check_business_inputs(readiness, context=changed, documents=documents)
    assert "context_fact_identity_mismatch" in {g["code"] for g in result["gates"]}
    assert result["er_diagnostic"]["status"] == "blocked"
    incomplete = context.model_copy(
        update={
            "period_fact_ids": {
                f: i for f, i in context.period_fact_ids.items() if f != "le_value_tco2e"
            }
        }
    )
    assert (
        check_business_inputs(readiness, context=incomplete, documents=documents)["er_diagnostic"][
            "status"
        ]
        == "blocked"
    )


def test_unknown_authority_and_bad_evidence_block(tmp_path):
    readiness, context, documents = fixture_context(tmp_path)
    changed = context.model_copy(update={"authority_confirmed": False})
    assert (
        check_business_inputs(readiness, context=changed, documents=documents)["er_diagnostic"][
            "status"
        ]
        == "blocked"
    )
    changed = context.model_copy(
        update={"evidence": (context.evidence[0].model_copy(update={"quote": "invented"}),)}
    )
    result = check_business_inputs(readiness, context=changed, documents=documents)
    assert "context_evidence_not_grounded" in {g["code"] for g in result["gates"]}


def test_zero_denominator_and_units_are_not_guessed(tmp_path):
    readiness, context, documents = fixture_context(tmp_path, reported=0)
    result = check_business_inputs(readiness, context=context, documents=documents)
    assert result["er_diagnostic"]["absolute_error_pct"] is None
    readiness["facts"]["pe_value_tco2e"]["unit"] = "kgCO2e"
    assert (
        check_business_inputs(readiness, context=context, documents=documents)["er_diagnostic"][
            "status"
        ]
        == "blocked"
    )


def test_period_format_and_order_rejected(tmp_path):
    _, context, _ = fixture_context(tmp_path)
    for start in ("2020", "2021-01-01"):
        with pytest.raises(ValidationError):
            AssessmentContext.model_validate({**context.model_dump(), "period_start": start})


def test_cli_reuse_and_stale_readiness_are_detected(tmp_path):
    engine, request = setup(tmp_path)
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
        str(tmp_path / "readiness"),
    ]
    readiness = json.loads(runner.invoke(app, args).stdout)
    check_args = [
        "score",
        "checks",
        readiness["artifact_path"],
        "--database",
        str(tmp_path / "db.sqlite"),
        "--output-dir",
        str(tmp_path / "checks"),
    ]
    first = runner.invoke(app, check_args)
    assert first.exit_code == 0, first.exception
    assert json.loads(runner.invoke(app, check_args).stdout)["status"] == "reused"
    decide(engine, request)
    stale = runner.invoke(app, check_args)
    assert stale.exit_code == 1
