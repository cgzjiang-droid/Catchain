from pathlib import Path

import pytest

from catchain.ingestion.raw_store import RawBlobStore

FIXTURE_BYTES = b"CATchain raw fixture\n"
FIXTURE_SHA256 = "4ab4b9d242e191b238c1c84129367a163b8493e87d953febc8e92ab1dbc52d47"


def test_store_file_preserves_bytes_under_their_sha256(tmp_path: Path) -> None:
    source = tmp_path / "project.pdf"
    source.write_bytes(FIXTURE_BYTES)
    raw_root = tmp_path / "raw"

    stored = RawBlobStore(raw_root).store_file(source)

    assert stored.sha256 == FIXTURE_SHA256
    assert stored.byte_size == len(FIXTURE_BYTES)
    assert stored.path == raw_root / FIXTURE_SHA256[:2] / FIXTURE_SHA256
    assert stored.path.read_bytes() == FIXTURE_BYTES
    assert stored.created is True


def test_store_file_reuses_identical_content(tmp_path: Path) -> None:
    first_source = tmp_path / "first.pdf"
    second_source = tmp_path / "second.pdf"
    first_source.write_bytes(FIXTURE_BYTES)
    second_source.write_bytes(FIXTURE_BYTES)
    store = RawBlobStore(tmp_path / "raw")

    first = store.store_file(first_source)
    second = store.store_file(second_source)

    assert second.path == first.path
    assert second.sha256 == first.sha256
    assert second.created is False
    assert list((tmp_path / "raw").rglob(FIXTURE_SHA256)) == [first.path]


def test_store_file_rejects_a_missing_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RawBlobStore(tmp_path / "raw").store_file(tmp_path / "missing.pdf")


def test_store_file_rejects_a_directory(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        RawBlobStore(tmp_path / "raw").store_file(tmp_path)


def test_store_file_rejects_an_empty_source(tmp_path: Path) -> None:
    source = tmp_path / "empty.pdf"
    source.touch()

    with pytest.raises(ValueError, match="empty"):
        RawBlobStore(tmp_path / "raw").store_file(source)
