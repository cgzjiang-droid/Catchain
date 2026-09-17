"""Immutable content-addressed storage for raw source bytes."""

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from catchain.domain import Sha256


@dataclass(frozen=True, slots=True)
class StoredRawBlob:
    """The traceable result of storing one raw file."""

    sha256: Sha256
    byte_size: int
    path: Path
    created: bool


class RawBlobStore:
    """Store immutable bytes at paths derived from their SHA-256 digest."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for_hash(self, sha256: Sha256) -> Path:
        """Return the stable content-addressed path for a known hash."""
        return self.root / sha256[:2] / sha256

    def store_file(self, source: Path) -> StoredRawBlob:
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(source)
        if not source.is_file():
            raise IsADirectoryError(source)

        self.root.mkdir(parents=True, exist_ok=True)
        staging_dir = self.root / ".staging"
        staging_dir.mkdir(exist_ok=True)
        file_descriptor, staged_name = tempfile.mkstemp(prefix="raw-", dir=staging_dir)
        staged_path = Path(staged_name)

        digest = hashlib.sha256()
        byte_size = 0
        try:
            with source.open("rb") as input_file, os.fdopen(file_descriptor, "wb") as staged_file:
                while chunk := input_file.read(1024 * 1024):
                    digest.update(chunk)
                    staged_file.write(chunk)
                    byte_size += len(chunk)

            if byte_size == 0:
                raise ValueError(f"raw source is empty: {source}")

            sha256 = digest.hexdigest()
            destination = self.path_for_hash(sha256)
            destination.parent.mkdir(parents=True, exist_ok=True)

            try:
                os.link(staged_path, destination)
                created = True
            except FileExistsError:
                created = False

            return StoredRawBlob(
                sha256=sha256,
                byte_size=byte_size,
                path=destination,
                created=created,
            )
        finally:
            staged_path.unlink(missing_ok=True)
