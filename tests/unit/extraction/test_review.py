import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_validation import fixture
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain import DocumentVersion, PipelineRun, PipelineStage, RunStatus, SourceDocument
from catchain.domain.review import ReviewRequest
from catchain.storage.database import (
    canonical_fact_sources,
    canonical_facts,
    canonical_heads,
    create_schema,
    create_sqlite_engine,
    fact_candidates,
    review_decisions,
)
from catchain.storage.document_repository import SqlAlchemyDocumentRepository
from catchain.storage.fact_repository import SqlAlchemyFactRepository
from catchain.storage.review_repository import ReviewBlocked, decide
from catchain.validation.extraction import validate_extraction


def setup(tmp_path, field="project_name", value="Example"):
    parsed, extraction = fixture(field, value)
    engine = create_sqlite_engine(tmp_path / "db.sqlite")
    create_schema(engine)
    documents = SqlAlchemyDocumentRepository(engine)
    now = datetime.now(UTC)
    source = SourceDocument(
        registry=extraction.registry,
        registry_project_id=extraction.project_id,
        source_url="https://example.org/a.pdf",
        document_type="other",
        discovered_at=now,
    )
    documents.add_source(source)
    documents.add_version(
        DocumentVersion(
            document_version_id=parsed.document_version_id,
            source_document_id=source.source_document_id,
            sha256="a" * 64,
            retrieved_at=now,
            content_type="application/pdf",
            file_name="a.pdf",
            byte_size=1,
        )
    )
    documents.add_parsed(parsed, configuration_hash="b" * 64)
    report = validate_extraction(parsed, extraction, pipeline_run_id=uuid4())
    common = dict(
        status=RunStatus.SUCCEEDED,
        input_hash=hashlib.sha256(parsed.model_dump_json().encode()).hexdigest(),
        config_hash="c" * 64,
        started_at=now,
        finished_at=now,
    )
    SqlAlchemyFactRepository(engine).import_validation(
        report,
        PipelineRun(
            pipeline_run_id=report.pipeline_run_id, stage=PipelineStage.QUALITY_VALIDATED, **common
        ),
        extraction,
        PipelineRun(
            pipeline_run_id=extraction.pipeline_run_id,
            stage=PipelineStage.BASELINE_EXTRACTED,
            **common,
        ),
    )
    with engine.connect() as connection:
        candidate = connection.execute(
            select(fact_candidates.c.candidate_id).where(
                fact_candidates.c.validation_run_id == str(report.pipeline_run_id)
            )
        ).scalar_one()
    request = ReviewRequest(
        decision_id=uuid4(),
        candidate_id=candidate,
        reviewer="test-reviewer",
        reason="Test fixture review",
        status="approved",
        authority_confirmed=True,
        after=extraction.observations[0],
    )
    return engine, request


def test_approval_history_reuse_and_stale_write(tmp_path):
    engine, request = setup(tmp_path)
    first = decide(engine, request)
    assert first["canonical_writes"] == 1
    assert decide(engine, request)["status"] == "reused"
    with pytest.raises(ReviewBlocked, match="decision_id_conflict"):
        decide(engine, request.model_copy(update={"reason": "changed"}))
    with pytest.raises(ReviewBlocked, match="stale_current_fact"):
        decide(engine, request.model_copy(update={"decision_id": uuid4()}))
    replacement = request.model_copy(
        update={
            "decision_id": uuid4(),
            "expected_current_fact_id": UUID(first["fact_id"]),
            "after": request.after.model_copy(update={"normalized_value": "Revised"}),
        }
    )
    second = decide(engine, replacement)
    with engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(canonical_facts)).scalar_one() == 2
        )
        assert (
            connection.execute(select(canonical_heads.c.fact_id)).scalar_one() == second["fact_id"]
        )
        source = connection.execute(
            select(canonical_fact_sources).where(
                canonical_fact_sources.c.fact_id == second["fact_id"]
            )
        ).mappings().one()
        assert source["document_version_id"] == str(request.after.evidence[0].document_version_id)
        decision = (
            connection.execute(
                select(review_decisions).where(
                    review_decisions.c.decision_id == str(replacement.decision_id)
                )
            )
            .mappings()
            .one()
        )
        assert json.loads(decision["before_value_json"]) == "Example"
        assert json.loads(decision["after_value_json"]) == "Revised"


@pytest.mark.parametrize("status", ["unresolved", "rejected"])
def test_nonapproval_preserves_formal_value(tmp_path, status):
    engine, request = setup(tmp_path)
    first = decide(engine, request)
    decision = ReviewRequest(
        decision_id=uuid4(),
        candidate_id=request.candidate_id,
        reviewer="test-reviewer",
        reason="Cannot establish authority",
        status=status,
        expected_current_fact_id=first["fact_id"],
    )
    assert decide(engine, decision)["canonical_writes"] == 0
    with engine.connect() as connection:
        assert (
            connection.execute(select(canonical_heads.c.fact_id)).scalar_one() == first["fact_id"]
        )


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("registered_date", "2020", "date_format_unresolved"),
        ("installed_capacity_mw", 12, "unit_unverified"),
    ],
)
def test_human_approval_cannot_bypass_mechanical_rules(tmp_path, field, value, code):
    engine, request = setup(tmp_path, field, value)
    with pytest.raises(ReviewBlocked, match=code):
        decide(engine, request)
    with engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(review_decisions)).scalar_one() == 0
        )


def test_bad_quote_is_blocked_and_cli_preserves_draft(tmp_path):
    engine, request = setup(tmp_path)
    ref = request.after.evidence[0].model_copy(update={"quote": "invented"})
    bad = request.model_copy(
        update={"after": request.after.model_copy(update={"evidence": (ref,)})}
    )
    path = tmp_path / "request.json"
    path.write_text(bad.model_dump_json())
    result = CliRunner().invoke(
        app,
        [
            "review",
            "decide",
            str(path),
            "--database",
            str(tmp_path / "db.sqlite"),
            "--draft-dir",
            str(tmp_path / "drafts"),
        ],
    )
    assert result.exit_code == 1
    outcome = json.loads(result.stdout)
    assert outcome["status"] == "draft" and outcome["canonical_writes"] == 0
    draft = json.loads(Path(outcome["draft_path"]).read_text())
    assert draft["raw_request"] == path.read_text()
    assert any(e["code"] == "evidence_quote_missing" for e in draft["errors"])


def test_reversed_dates_cannot_become_formal_pair(tmp_path):
    engine, start = setup(tmp_path, "crediting_period_start", "2022-01-01")
    decide(engine, start)
    engine, end = setup(tmp_path, "crediting_period_end", "2021-01-01")
    with pytest.raises(ReviewBlocked, match="date_order_reversed"):
        decide(engine, end)


def test_approval_transaction_rolls_back_if_fact_write_fails(tmp_path):
    from sqlalchemy import event

    engine, request = setup(tmp_path)

    def fail(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO canonical_facts"):
            raise RuntimeError("simulated fact storage failure")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="simulated"):
            decide(engine, request)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with engine.connect() as connection:
        assert (
            connection.execute(select(func.count()).select_from(review_decisions)).scalar_one() == 0
        )
        assert (
            connection.execute(select(func.count()).select_from(canonical_facts)).scalar_one() == 0
        )


def test_invalid_required_field_preserves_error_location(tmp_path):
    path = tmp_path / "request.json"
    path.write_text(json.dumps({"reviewer": 123}))
    result = CliRunner().invoke(
        app, ["review", "decide", str(path), "--draft-dir", str(tmp_path / "drafts")]
    )
    assert result.exit_code == 1
    outcome = json.loads(result.stdout)
    assert any(e["loc"] == ["reviewer"] for e in outcome["errors"])


def test_cli_candidate_listing_and_approval(tmp_path):
    engine, request = setup(tmp_path)
    with engine.connect() as connection:
        run_id = connection.execute(select(fact_candidates.c.validation_run_id)).scalar_one()
    runner = CliRunner()
    listed = runner.invoke(
        app, ["review", "candidates", run_id, "--database", str(tmp_path / "db.sqlite")]
    )
    assert listed.exit_code == 0, listed.exception
    item = json.loads(listed.stdout)["candidates"][0]
    assert item["candidate_id"] == str(request.candidate_id)
    assert item["expected_current_fact_id"] is None
    path = tmp_path / "request.json"
    path.write_text(request.model_dump_json())
    result = runner.invoke(
        app, ["review", "decide", str(path), "--database", str(tmp_path / "db.sqlite")]
    )
    assert result.exit_code == 0, result.exception
    assert json.loads(result.stdout)["canonical_writes"] == 1
