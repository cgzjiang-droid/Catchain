import json
from pathlib import Path

from typer.testing import CliRunner


def test_generate_json_schemas_exports_public_models(tmp_path: Path) -> None:
    from catchain.schema_export import generate_json_schemas

    written = generate_json_schemas(tmp_path)

    assert [path.name for path in written] == [
        "assessment-context.schema.json",
        "document-version.schema.json",
        "evaluation-result.schema.json",
        "evidence-ref.schema.json",
        "extraction-validation-report.schema.json",
        "field-observation.schema.json",
        "gold-sample.schema.json",
        "judgment-request.schema.json",
        "parsed-document.schema.json",
        "pipeline-run.schema.json",
        "project-consistency-report.schema.json",
        "project-extraction.schema.json",
        "review-request.schema.json",
        "source-document.schema.json",
    ]
    source_schema = json.loads(
        (tmp_path / "source-document.schema.json").read_text(encoding="utf-8")
    )
    assert source_schema["title"] == "SourceDocument"
    assert source_schema["additionalProperties"] is False
    assert "registry_project_id" in source_schema["properties"]


def test_generate_json_schemas_is_deterministic(tmp_path: Path) -> None:
    from catchain.schema_export import generate_json_schemas

    first_paths = generate_json_schemas(tmp_path)
    first_contents = {path.name: path.read_bytes() for path in first_paths}

    second_paths = generate_json_schemas(tmp_path)
    second_contents = {path.name: path.read_bytes() for path in second_paths}

    assert second_contents == first_contents


def test_schema_export_cli_reports_written_files(tmp_path: Path) -> None:
    from catchain.cli import app

    runner = CliRunner()

    result = runner.invoke(app, ["schema", "export", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Exported 14 schemas" in result.stdout
