import json
from pathlib import Path

import pymupdf
from typer.testing import CliRunner

from catchain.cli import app
from catchain.extraction.llm.providers import ProviderReply


def test_llm_cli_import_parse_and_extract_uses_source_identity(tmp_path, monkeypatch):
    pdf = tmp_path / "project.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Project title: Example Wind Project")
        document.save(pdf)
    runner = CliRunner()
    database, raw, output = tmp_path / "db.sqlite", tmp_path / "raw", tmp_path / "out"
    common = ["--database", str(database), "--raw-root", str(raw)]
    imported = runner.invoke(
        app,
        [
            "ingest",
            "local",
            str(pdf),
            "--registry",
            "verra",
            "--project-id",
            "VCS1",
            "--source-url",
            "https://example.org/test.pdf",
            "--document-type",
            "project_description",
            *common,
        ],
    )
    assert imported.exit_code == 0, imported.exception
    version = imported.stdout.split("Document version ID: ")[1].splitlines()[0]
    parsed = runner.invoke(app, ["parse", "raw", version, *common, "--min-non-whitespace", "0"])
    assert parsed.exit_code == 0, parsed.exception
    parsed_id = json.loads(parsed.stdout)["parsed_document_id"]
    calls = []

    def fake_extract(self, **kwargs):
        calls.append(kwargs)
        return ProviderReply(
            response_id="fixture-cli",
            model="deepseek-flash",
            finish_reason="stop",
            input_tokens=40,
            output_tokens=20,
            latency_seconds=0.01,
            content=json.dumps(
                {
                    "observations": [
                        {
                            "field_name": "project_name",
                            "raw_value": "Example Wind Project",
                            "normalized_value": "Example Wind Project",
                            "unit": None,
                            "missing_reason": None,
                            "evidence": [
                                {
                                    "page_number": 1,
                                    "quote": "Project title: Example Wind Project",
                                }
                            ],
                        }
                    ]
                }
            ),
        )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-key")
    monkeypatch.setattr("catchain.extraction.llm.providers.DeepSeekProvider.extract", fake_extract)
    args = [
        "extract",
        "llm-once",
        parsed_id,
        "--page",
        "1",
        "--field",
        "project_name",
        "--database",
        str(database),
        "--output-dir",
        str(output),
    ]
    extracted = runner.invoke(app, args)
    assert extracted.exit_code == 0, extracted.exception
    info = json.loads(extracted.stdout)
    artifact = json.loads(Path(info["artifact_path"]).read_text())
    assert info["project_id"] == artifact["result"]["project_id"] == "VCS1"
    assert artifact["result"]["document_version_id"] == version
    assert info["cache_enabled"] is False and len(calls) == 1
    assert artifact["result"]["observations"][0]["validation_status"] == "unvalidated"
    invalid = runner.invoke(app, [*args, "--page", "2"])
    assert invalid.exit_code == 1
    assert len(calls) == 1
