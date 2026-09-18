"""Immutable object-storage boundary with a local implementation for development."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO

from catchain.domain import Sha256


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    sha256: Sha256
    byte_size: int
    created: bool


class LocalObjectStore:
    """Content-addressed object store used by dev and as the S3 contract reference."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not key or key.startswith("/") or ".." in Path(key).parts:
            raise ValueError("object key must be relative and traversal-free")
        return self.root / key

    def put_immutable(self, key: str, source: BinaryIO, expected_sha256: Sha256) -> StoredObject:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        byte_size = 0
        with NamedTemporaryFile(dir=destination.parent, delete=False) as staged:
            temporary = Path(staged.name)
            try:
                while chunk := source.read(8 * 1024 * 1024):
                    digest.update(chunk)
                    staged.write(chunk)
                    byte_size += len(chunk)
                actual = digest.hexdigest()
                if actual != expected_sha256:
                    raise ValueError("object SHA-256 does not match expected hash")
                staged.flush()
                os.fsync(staged.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.link(temporary, destination)
            created = True
        except FileExistsError:
            created = False
        finally:
            temporary.unlink(missing_ok=True)
        return StoredObject(key=key, sha256=expected_sha256, byte_size=byte_size, created=created)

    def open(self, key: str):
        return self._path(key).open("rb")

