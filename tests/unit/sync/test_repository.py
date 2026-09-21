from datetime import UTC, datetime

from catchain.domain import Registry
from catchain.storage.database import create_schema, create_sqlite_engine
from catchain.storage.sync_repository import SyncRepository
from catchain.sync.service import SyncCheckpoint, SyncFailure, SyncReport


def _report(*, failures: tuple[SyncFailure, ...], next_cursor: str | None) -> SyncReport:
    return SyncReport(
        discovered_projects=1,
        discovered_documents=(),
        next_checkpoint=SyncCheckpoint(next_cursor),
        failures=failures,
    )


def test_failed_page_does_not_advance_checkpoint_and_is_replayable(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "sync.sqlite")
    create_schema(engine)
    repository = SyncRepository(engine)
    before = SyncCheckpoint("cursor-1")
    report = _report(
        failures=(SyncFailure(scope="registry", code="http_403", message="denied"),),
        next_cursor="cursor-2",
    )

    record = repository.record_run(
        registry=Registry.GOLD_STANDARD,
        checkpoint_before=before,
        report=report,
        started_at=datetime(2026, 9, 21, tzinfo=UTC),
        finished_at=datetime(2026, 9, 21, 0, 0, 1, tzinfo=UTC),
    )

    assert record.status == "failed"
    assert repository.load_checkpoint(Registry.GOLD_STANDARD).cursor == "cursor-1"
    assert repository.latest_run(Registry.GOLD_STANDARD).failures[0].code == "http_403"


def test_successful_page_advances_checkpoint(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "sync.sqlite")
    create_schema(engine)
    repository = SyncRepository(engine)
    report = _report(failures=(), next_cursor="cursor-2")

    record = repository.record_run(
        registry=Registry.VERRA,
        checkpoint_before=SyncCheckpoint(None),
        report=report,
        started_at=datetime(2026, 9, 21, tzinfo=UTC),
        finished_at=datetime(2026, 9, 21, 0, 0, 1, tzinfo=UTC),
    )

    assert record.status == "succeeded"
    assert repository.load_checkpoint(Registry.VERRA).cursor == "cursor-2"
