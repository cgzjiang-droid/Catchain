import json
from uuid import uuid4

import pymupdf
from sqlalchemy import select
from typer.testing import CliRunner

from catchain.cli import app
from catchain.domain import PipelineRun, ProjectExtraction
from catchain.storage import create_sqlite_engine
from catchain.storage.database import document_versions


def test_baseline_cli_chain_reuses_artifacts_and_rejects_corruption(tmp_path):
    pdf = tmp_path / "project.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text(
            (72, 72),
            "Project title: Example Wind Project\nHost country: Brazil\n"
            "Installed capacity: 12.5 MW\nGrid-connected project boundary applicability",
        )
        document.save(pdf)
    database = tmp_path / "catchain.sqlite"
    raw = tmp_path / "raw"
    out = tmp_path / "extracted"
    runner = CliRunner()
    imported = runner.invoke(
        app,
        [
            "ingest",
            "local",
            str(pdf),
            "--registry",
            "verra",
            "--project-id",
            "VCS7",
            "--source-url",
            "https://example.org/pdd.pdf",
            "--document-type",
            "project_description",
            "--database",
            str(database),
            "--raw-root",
            str(raw),
        ],
    )
    assert imported.exit_code == 0, imported.exception
    with create_sqlite_engine(database).connect() as connection:
        version = connection.scalar(select(document_versions.c.document_version_id))
    assert f"Document version ID: {version}" in imported.stdout
    parsed = runner.invoke(
        app,
        [
            "parse",
            "raw",
            version,
            "--database",
            str(database),
            "--raw-root",
            str(raw),
            "--min-non-whitespace",
            "0",
        ],
    )
    assert parsed.exit_code == 0, parsed.exception
    parsed_id = json.loads(parsed.stdout)["parsed_document_id"]
    common = [parsed_id, "--database", str(database), "--output-dir", str(out)]
    extract_args = ["extract", "baseline", *common, "--project-id", "VCS7", "--registry", "verra"]
    for args in [extract_args, ["score", "keywords", *common]]:
        first = runner.invoke(app, args)
        assert first.exit_code == 0, first.exception
        info = json.loads(first.stdout)
        path = out / info["artifact_name"]
        before = path.read_bytes()
        second = runner.invoke(app, args)
        assert second.exit_code == 0, second.exception
        reused = json.loads(second.stdout)
        assert info["status"] == "stored" and reused["status"] == "reused"
        assert reused["pipeline_run_id"] == info["pipeline_run_id"]
        assert path.read_bytes() == before
        artifact = json.loads(before)
        run = PipelineRun.model_validate(artifact["run"])
        assert str(run.pipeline_run_id) == artifact["result"]["pipeline_run_id"]
        if args == extract_args:
            result = ProjectExtraction.model_validate(artifact["result"])
            assert str(result.document_version_id) == version
            assert any(o.normalized_value == 12.5 for o in result.observations)
        else:
            assert artifact["result"]["dimensions"][0]["score"] == 3
        path.write_text("{}")
        failed = runner.invoke(app, args)
        assert failed.exit_code == 1
        assert json.loads(failed.stdout)["error_code"] == "ARTIFACT_CONFLICT"
        assert path.read_text() == "{}"
    wrong = runner.invoke(
        app, ["extract", "baseline", *common, "--project-id", "wrong", "--registry", "verra"]
    )
    assert wrong.exit_code == 1
    assert json.loads(wrong.stdout)["error_code"] == "SOURCE_IDENTITY_MISMATCH"
    assert len(list(out.glob("*.json"))) == 2


def test_unknown_parsed_id_does_not_write_artifact(tmp_path):
    for prefix in [["extract", "baseline"], ["score", "keywords"]]:
        args = [
            *prefix,
            str(uuid4()),
            "--database",
            str(tmp_path / "db.sqlite"),
            "--output-dir",
            str(tmp_path / "out"),
        ]
        if prefix[0] == "extract":
            args += ["--project-id", "VCS7", "--registry", "verra"]
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 1
        assert json.loads(result.stdout)["error_code"] == "PARSED_DOCUMENT_NOT_FOUND"
    assert not (tmp_path / "out").exists()
