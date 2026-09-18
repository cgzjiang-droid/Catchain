from datetime import UTC, datetime

from catchain.domain import DocumentType, Registry
from catchain.registries.base import DiscoveryPage, RemoteDocument, RemoteProject
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

