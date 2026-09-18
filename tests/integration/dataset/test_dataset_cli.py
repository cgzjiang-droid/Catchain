import json

from typer.testing import CliRunner

from catchain.cli import app


def test_dataset_cli_builds_manifest_and_sample(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    for index in range(4):
        (root / f"project-{index}.pdf").write_bytes(f"pdf-{index}".encode())
    manifest = tmp_path / "manifest.jsonl"
    sample = tmp_path / "sample.jsonl"
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["dataset", "manifest", str(root), "--output", str(manifest)],
    )
    assert result.exit_code == 0, result.exception
    assert json.loads(result.stdout)["row_count"] == 4

    result = runner.invoke(
        app,
        [
            "dataset",
            "sample",
            str(manifest),
            "--output",
            str(sample),
            "--development",
            "2",
            "--validation",
            "1",
            "--test",
            "1",
        ],
    )
    assert result.exit_code == 0, result.exception
    assert json.loads(result.stdout)["counts"]["test"] == 1
