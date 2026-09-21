from datetime import UTC, datetime

from catchain.domain import DocumentType, Registry
from catchain.registries.base import (
    DiscoveryPage,
    RegistryNotConfiguredError,
    RemoteDocument,
    RemoteProject,
)
from catchain.storage.database import create_schema, create_sqlite_engine
from catchain.storage.sync_repository import SyncRepository
from catchain.sync.service import SyncCheckpoint, SyncService


class FixtureAdapter:
    registry = Registry.VERRA

    def discover_projects(self, cursor=None):
        return DiscoveryPage(
            projects=(RemoteProject(Registry.VERRA, "VCS-1", "https://example.test/VCS-1"),),
            next_cursor="next" if cursor is None else None,
            complete=cursor is not None,
        )

    def list_documents(self, project_id):
        return (
            RemoteDocument(
                registry=Registry.VERRA,
                project_id=project_id,
                document_id="doc-1",
                document_type=DocumentType.OTHER,
                title="PDD",
                url="https://example.test/doc-1.pdf",
                discovered_at=datetime(2026, 9, 18, tzinfo=UTC),
            ),
        )


def test_sync_service_returns_checkpoint_and_documents() -> None:
    report = SyncService().run(FixtureAdapter(), SyncCheckpoint())

    assert report.discovered_projects == 1
    assert report.discovered_documents[0].document_id == "doc-1"
    assert report.next_checkpoint.cursor == "next"
    assert report.failures == ()


class BlockedAdapter:
    registry = Registry.GOLD_STANDARD

    def discover_projects(self, cursor=None):
        raise RegistryNotConfiguredError("gold_standard live endpoint blocked")

    def list_documents(self, project_id):
        raise AssertionError("list_documents must not run after discovery failure")


def test_sync_service_persists_discovery_failure_without_advancing_cursor(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "sync.sqlite")
    create_schema(engine)
    repository = SyncRepository(engine)
    report = SyncService().run(
        BlockedAdapter(),
        SyncCheckpoint("cursor-1"),
        repository=repository,
        started_at=datetime(2026, 9, 21, tzinfo=UTC),
        finished_at=datetime(2026, 9, 21, 0, 0, 1, tzinfo=UTC),
    )

    assert report.status == "failed"
    assert report.failures[0].code == "registry_not_configured"
    assert repository.load_checkpoint(Registry.GOLD_STANDARD).cursor == "cursor-1"
