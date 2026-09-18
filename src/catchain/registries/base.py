"""Provider-neutral registry adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Protocol

from catchain.domain import DocumentType, Registry, Sha256


class RegistryNotConfiguredError(RuntimeError):
    """Raised when a live registry endpoint has not passed smoke-test configuration."""


@dataclass(frozen=True, slots=True)
class RemoteProject:
    registry: Registry
    project_id: str
    project_url: str


@dataclass(frozen=True, slots=True)
class RemoteDocument:
    registry: Registry
    project_id: str
    document_id: str
    document_type: DocumentType
    title: str
    url: str
    discovered_at: datetime
    declared_version: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryPage:
    projects: tuple[RemoteProject, ...]
    next_cursor: str | None
    complete: bool


@dataclass(frozen=True, slots=True)
class DownloadReceipt:
    document_id: str
    status: str
    http_status: int
    sha256: Sha256 | None
    byte_size: int | None
    content_type: str | None
    retrieved_at: datetime
    error_code: str | None = None


class RegistryAdapter(Protocol):
    registry: Registry

    def discover_projects(self, cursor: str | None = None) -> DiscoveryPage: ...

    def list_documents(self, project_id: str) -> tuple[RemoteDocument, ...]: ...

    def download(self, document: RemoteDocument, destination: BinaryIO) -> DownloadReceipt: ...


def reject_live_operation(registry: Registry) -> None:
    """Make unverified live endpoints fail explicitly instead of returning empty data."""

    raise RegistryNotConfiguredError(
        f"{registry.value} live endpoint is not configured and smoke-tested"
    )

