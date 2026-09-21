"""Bounded, resumable registry discovery workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from catchain.registries.base import RegistryAdapter, RegistryNotConfiguredError, RemoteDocument

if TYPE_CHECKING:
    from catchain.storage.sync_repository import SyncRepository


@dataclass(frozen=True, slots=True)
class SyncCheckpoint:
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class SyncFailure:
    scope: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class SyncReport:
    discovered_projects: int
    discovered_documents: tuple[RemoteDocument, ...]
    next_checkpoint: SyncCheckpoint
    failures: tuple[SyncFailure, ...]

    @property
    def status(self) -> str:
        if not self.failures:
            return "succeeded"
        if any(failure.scope == "registry" for failure in self.failures):
            return "failed"
        return "partial" if self.discovered_projects else "failed"


class SyncService:
    """Discover projects and documents without conflating failures with emptiness."""

    def run(
        self,
        adapter: RegistryAdapter,
        checkpoint: SyncCheckpoint,
        *,
        repository: SyncRepository | None = None,
        started_at=None,
        finished_at=None,
    ) -> SyncReport:
        if started_at is None:
            from datetime import UTC, datetime

            started_at = datetime.now(UTC)
        failures: list[SyncFailure] = []
        try:
            page = adapter.discover_projects(checkpoint.cursor)
        except Exception as error:  # noqa: BLE001 - persisted as a registry-scoped failure
            report = SyncReport(
                discovered_projects=0,
                discovered_documents=(),
                next_checkpoint=checkpoint,
                failures=(
                    SyncFailure(
                        scope="registry",
                        code=_error_code(error),
                        message=_error_message(error),
                    ),
                ),
            )
            if repository is not None:
                repository.record_run(
                    registry=adapter.registry,
                    checkpoint_before=checkpoint,
                    report=report,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            return report
        documents: list[RemoteDocument] = []
        for project in page.projects:
            try:
                documents.extend(adapter.list_documents(project.project_id))
            except Exception as error:  # noqa: BLE001 - persisted as a project-scoped failure
                failures.append(
                    SyncFailure(
                        scope=project.project_id,
                        code=_error_code(error),
                        message=_error_message(error),
                    )
                )
        report = SyncReport(
            discovered_projects=len(page.projects),
            discovered_documents=tuple(documents),
            next_checkpoint=SyncCheckpoint(page.next_cursor),
            failures=tuple(failures),
        )
        if repository is not None:
            repository.record_run(
                registry=adapter.registry,
                checkpoint_before=checkpoint,
                report=report,
                started_at=started_at,
                finished_at=finished_at,
            )
        return report


def _error_code(error: Exception) -> str:
    if isinstance(error, RegistryNotConfiguredError):
        return "registry_not_configured"
    if isinstance(error, TimeoutError):
        return "timeout"
    return type(error).__name__.lower()


def _error_message(error: Exception) -> str:
    message = str(error).strip()
    return message or type(error).__name__
