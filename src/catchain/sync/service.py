"""Bounded, resumable registry discovery workflow."""

from __future__ import annotations

from dataclasses import dataclass

from catchain.registries.base import RegistryAdapter, RemoteDocument


@dataclass(frozen=True, slots=True)
class SyncCheckpoint:
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class SyncReport:
    discovered_projects: int
    discovered_documents: tuple[RemoteDocument, ...]
    next_checkpoint: SyncCheckpoint
    failures: tuple[str, ...]


class SyncService:
    """Discover projects and documents without conflating failures with emptiness."""

    def run(self, adapter: RegistryAdapter, checkpoint: SyncCheckpoint) -> SyncReport:
        page = adapter.discover_projects(checkpoint.cursor)
        documents: list[RemoteDocument] = []
        failures: list[str] = []
        for project in page.projects:
            try:
                documents.extend(adapter.list_documents(project.project_id))
            except Exception as error:  # noqa: BLE001 - persisted as a project-scoped failure
                failures.append(f"{project.project_id}:discovery_failed:{type(error).__name__}")
        return SyncReport(
            discovered_projects=len(page.projects),
            discovered_documents=tuple(documents),
            next_checkpoint=SyncCheckpoint(page.next_cursor),
            failures=tuple(failures),
        )

