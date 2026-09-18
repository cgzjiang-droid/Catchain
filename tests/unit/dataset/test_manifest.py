import json

import pytest

from catchain.dataset import build_manifest, iter_manifest_rows, sample_manifest


def test_manifest_hashes_files_streaming_and_infers_project(tmp_path):
    root = tmp_path / "corpus"
    (root / "ACR125").mkdir(parents=True)
    (root / "ACR125" / "project.pdf").write_bytes(b"pdf-a")
    (root / "ACR125" / "notes.txt").write_text("notes", encoding="utf-8")
    output = tmp_path / "manifest.jsonl"

    header = build_manifest(root, output)

    assert header.row_count == 2
    assert header.total_bytes == 10
    rows = list(iter_manifest_rows(output))
    assert {row.project_id for row in rows} == {"ACR125"}
    assert rows[0].sha256 != rows[1].sha256
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[0])["row_count"] == 2


def test_manifest_excludes_hidden_files_and_rejects_non_directory(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (root / ".secret.pdf").write_bytes(b"hidden")
    output = tmp_path / "manifest.jsonl"
    assert build_manifest(root, output).row_count == 0
    with pytest.raises(ValueError, match="not a directory"):
        build_manifest(tmp_path / "missing", output)


def test_sampling_is_deterministic_and_assigns_requested_splits(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    for index in range(10):
        (root / f"project-{index}.pdf").write_bytes(f"{index}".encode())
    manifest = tmp_path / "manifest.jsonl"
    build_manifest(root, manifest)
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"

    assert sample_manifest(manifest, first, development=3, validation=1, test=1, seed=7) == {
        "development": 3,
        "validation": 1,
        "test": 1,
    }
    sample_manifest(manifest, second, development=3, validation=1, test=1, seed=7)
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert {row.sample_split for row in iter_manifest_rows(first)} == {
        "development",
        "validation",
        "test",
    }


def test_sampling_rejects_short_manifest(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "one.pdf").write_bytes(b"one")
    manifest = tmp_path / "manifest.jsonl"
    build_manifest(root, manifest)
    with pytest.raises(ValueError, match="requested"):
        sample_manifest(manifest, tmp_path / "sample.jsonl", development=2, validation=0, test=0)

