"""Streaming SHA-256 manifests for large local datasets."""

import hashlib
import json
import mimetypes
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from catchain.dataset.models import DatasetManifestHeader, ManifestRow
from catchain.domain.documents import DocumentType, Registry

_CHUNK_SIZE = 8 * 1024 * 1024


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _iter_files(root: Path, excluded: Path) -> Iterator[Path]:
    for current, directories, files in os.walk(root):
        directories[:] = sorted(
            directory for directory in directories if not directory.startswith(".")
        )
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = Path(current) / name
            if path.resolve() == excluded:
                continue
            if path.is_file() and not path.is_symlink():
                yield path


def build_manifest(
    root: Path,
    output: Path,
    *,
    registry: Registry | None = None,
    project_id: str | None = None,
    document_type: DocumentType | None = None,
    declared_version: str | None = None,
) -> DatasetManifestHeader:
    """Hash files one at a time and write a JSONL manifest without loading the corpus."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"dataset root is not a directory: {root}")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    total_bytes = 0
    generated_at = datetime.now(UTC)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    DatasetManifestHeader(
                        root_label=str(root),
                        generated_at=generated_at,
                        row_count=0,
                        total_bytes=0,
                    ).model_dump(mode="json"),
                    ensure_ascii=False,
                )
                + "\n"
            )
            for path in _iter_files(root, output):
                digest, size = _hash_file(path)
                relative = path.relative_to(root).as_posix()
                inferred_project = project_id
                if inferred_project is None and path.parent != root:
                    inferred_project = path.relative_to(root).parts[0]
                row = ManifestRow(
                    relative_path=relative,
                    size_bytes=size,
                    sha256=digest,
                    content_type=_content_type(path),
                    registry=registry,
                    project_id=inferred_project,
                    document_type=document_type,
                    declared_version=declared_version,
                )
                stream.write(json.dumps(row.model_dump(mode="json"), ensure_ascii=False) + "\n")
                row_count += 1
                total_bytes += size
            stream.flush()
            os.fsync(stream.fileno())
        header = DatasetManifestHeader(
            root_label=str(root),
            generated_at=generated_at,
            row_count=row_count,
            total_bytes=total_bytes,
        )
        content = temporary.read_text(encoding="utf-8").splitlines()
        content[0] = json.dumps(header.model_dump(mode="json"), ensure_ascii=False)
        temporary.write_text("\n".join(content) + "\n", encoding="utf-8")
        os.replace(temporary, output)
        return header
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def iter_manifest_rows(path: Path) -> Iterator[ManifestRow]:
    with path.open("r", encoding="utf-8") as stream:
        first = stream.readline()
        if not first:
            raise ValueError("manifest is empty")
        DatasetManifestHeader.model_validate_json(first)
        for line in stream:
            if line.strip():
                yield ManifestRow.model_validate_json(line)
